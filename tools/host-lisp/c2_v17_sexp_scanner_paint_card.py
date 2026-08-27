#!/usr/bin/env python3
"""Permanent gate for v1.7 Block-3 card 1: matcher and paint ownership."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"

import bytecode_p0 as VM  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_v17_editing_surface_polish_pricing as PRICE  # noqa: E402
import evidence_era as ERA  # noqa: E402


CONTRACT = ROOT / "config/c2-v17-sexp-scanner-paint-card-contract.json"
SOURCE = ROOT / "lib/sexp-depth.lisp"
IDE_SYNTAX = ROOT / "lib/ide-syntax.lisp"
SHIP_INPUT_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
CORE_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json"
LEGACY_CORE_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-core-subset.json"
LEGACY_STDLIB_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-subset.json"
LEGACY_WORKBENCH_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-werkbank-subset.json"
COMFORT_DELTA_SUITE = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
M65_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-m65-hw-base.json"
STDLIB_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-subset.json"
FASL_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-fasl-subset.json"
WORKBENCH_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json"
IDE_SUITE = ROOT / "tests/bytecode/libs/p0-ide-core-lib.json"
PRICING = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.7-editing-surface-polish-pricing-receipt.json")
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.7-sexp-scanner-paint-card-receipt.json")
METADATA_INDEX = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                         "v11-function-metadata-index.json")
METADATA_RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                           "v11-function-metadata-contract-receipt.json")
FORMAT = "lisp65-c2-v17-sexp-scanner-paint-card-receipt-v1"
SEALED_COMMIT = "0c1486a4"
FUNCTIONS = [
    "%sexp-code", "%sexp-rest", "%sexp-step", "%sexp-scan",
    "%sexp-open", "%sexp-close", "%sexp-match", "%sexp-paint",
]
PASS_NAMES = {"%sexp-scan", "%sexp-open", "%sexp-close"}
PAINT_OWNERS = {"%rl-idle", "%ide-idle"}
SUPPORT = "(defun nthcdr (n xs) (if (= n 0) xs (nthcdr (- n 1) (cdr xs))))\n"


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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def list_expr(values: list[int]) -> str:
    return "(quote (" + " ".join(str(value) for value in values) + "))"


def cases() -> list[dict[str, Any]]:
    nested = list_expr([40, 97, 32, 40, 98, 41, 41])
    quoted = list_expr([34, 97, 92, 34, 98, 34])
    return [
        {"name": "scan-list-hard-cap-three", "class": "chunk", "surface": "line",
         "expr": "(%sexp-scan (quote (40 40 40 40 97)) "
                 "(quote (40 40 40 40 97)) 5 0 0 nil)", "expect": "12"},
        {"name": "scan-string-hard-cap-three", "class": "chunk", "surface": "ide",
         "expr": "(%sexp-scan \"((((a\" nil 5 0 0 nil)", "expect": "12"},
        {"name": "scan-string-continuation", "class": "chunk", "surface": "ide",
         "expr": "(%sexp-scan \"((((a\" nil 5 3 12 nil)", "expect": "16"},
        {"name": "match-open-kind", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 40 0)", "expect": "1"},
        {"name": "match-close-kind", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 41 4)", "expect": "2"},
        {"name": "match-open-quote-kind", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 34 0)", "expect": "3"},
        {"name": "match-close-quote-kind", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 34 2)", "expect": "4"},
        {"name": "ordinary-code-bypasses", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 97 0)", "expect": "0"},
        {"name": "open-forward-first-chunk", "class": "partner", "surface": "line",
         "expr": f"(%sexp-close {nested} (nthcdr 1 {nested}) 7 1 4 41 nil)",
         "expect": "8"},
        {"name": "open-forward-second-chunk", "class": "partner", "surface": "line",
         "expr": f"(%sexp-close {nested} (nthcdr 4 {nested}) 7 4 8 41 nil)",
         "expect": "-7"},
        {"name": "close-prefix-two-chunks", "class": "partner", "surface": "line",
         "expr": f"(let ((p (%sexp-scan {nested} {nested} 6 0 0 nil))) "
                 f"(%sexp-scan {nested} (nthcdr 3 {nested}) 6 3 p nil))",
         "expect": "4"},
        {"name": "close-replay-first-chunk", "class": "partner", "surface": "line",
         "expr": f"(%sexp-open {nested} {nested} 6 0 0 1 40 nil)",
         "expect": "1025"},
        {"name": "close-replay-second-chunk", "class": "partner", "surface": "line",
         "expr": f"(mod (%sexp-open {nested} (nthcdr 3 {nested}) "
                 "6 3 1025 1 40 nil) 256)", "expect": "1"},
        {"name": "quote-forward-first-chunk", "class": "quote", "surface": "line",
         "expr": f"(%sexp-close {quoted} (nthcdr 1 {quoted}) 6 1 2 34 nil)",
         "expect": "2"},
        {"name": "quote-forward-second-chunk", "class": "quote", "surface": "line",
         "expr": f"(%sexp-close {quoted} (nthcdr 4 {quoted}) 6 4 2 34 nil)",
         "expect": "-6"},
        {"name": "quote-replay-first-chunk", "class": "quote", "surface": "line",
         "expr": f"(%sexp-open {quoted} {quoted} 5 0 0 0 34 nil)",
         "expect": "769"},
        {"name": "quote-replay-second-chunk", "class": "quote", "surface": "line",
         "expr": f"(mod (%sexp-open {quoted} (nthcdr 3 {quoted}) "
                 "5 3 769 0 34 nil) 256)", "expect": "1"},
        {"name": "paren-inside-string-hidden", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 40 (%sexp-scan (quote (34 40 34)) "
                 "(quote (34 40 34)) 1 0 0 nil))", "expect": "0"},
        {"name": "paren-after-comment-hidden", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 40 (%sexp-scan (quote (59 40)) "
                 "(quote (59 40)) 1 0 0 nil))", "expect": "0"},
        {"name": "escaped-quote-hidden", "class": "lexical", "surface": "shared",
         "expr": "(%sexp-match 34 (%sexp-scan (quote (34 92 34)) "
                 "(quote (34 92 34)) 2 0 0 nil))", "expect": "0"},
        {"name": "open-hard-cap-does-not-see-fourth", "class": "chunk", "surface": "shared",
         "expr": "(%sexp-open (quote (97 97 97 40)) (quote (97 97 97 40)) "
                 "4 0 0 1 40 nil)", "expect": "0"},
        {"name": "close-hard-cap-does-not-see-fourth", "class": "chunk", "surface": "shared",
         "expr": "(%sexp-close (quote (40 97 97 97 41)) "
                 "(quote (97 97 97 41)) 5 1 4 41 nil)", "expect": "4"},
        {"name": "composed-paint-transition", "class": "paint", "surface": "shared",
         "expr": "(%sexp-paint \"(a)(b)\" (cons 0 2) (cons 3 5) "
                 "0 4 80 3 0)", "expect": "nil",
         "expect_io_min": {"screen_put_char": 4}},
        {"name": "unmatched-clears-old-pair", "class": "paint", "surface": "shared",
         "expr": "(%sexp-paint \"(a)\" (cons 0 2) nil 0 4 80 10 0)",
         "expect": "nil", "expect_io_min": {"screen_put_char": 2}},
    ]


def compile_core(source: str) -> dict[str, Any]:
    return PRICE.compile_and_execute(
        SUPPORT + source, FUNCTIONS, cases(), "v1.7-sexp-scanner-paint-card",
        support_functions=("nthcdr",),
    )


class PaintVM(VM.P0VM):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.paint_calls: list[tuple[int, int, int, int]] = []

    def _callprim(self, prim_id: int, argc: int, stack: list[int], **kwargs: Any) -> int:
        if prim_id == 11 and argc == 4:
            args = stack[-argc:]
            self.paint_calls.append(tuple(VM.fixval(value) for value in args))
        return super()._callprim(prim_id, argc, stack, **kwargs)


def paint_trace(source: str) -> list[tuple[int, int, int, int]]:
    with tempfile.NamedTemporaryFile("w", suffix=".lisp", delete=False) as handle:
        path = Path(handle.name)
        handle.write(SUPPORT + source)
    try:
        suite = {
            "format": "lisp65-bytecode-p0-disk-lib-suite-v1",
            "name": "v17-paint-trace", "sources": [str(path)],
            "functions": ["nthcdr"] + FUNCTIONS,
            "strict_arity": True, "abi_profile": "dialect-v2", "max_call_args": 12,
            "cases": [{"name": "trace", "expr":
                       "(%sexp-paint \"(a)(b)\" (cons 0 2) (cons 3 5) "
                       "0 4 80 3 0)", "expect": "nil"}],
        }
        (heap, _names, _code, entry_flags, resident_flags, _bundle, directory,
         compiled_cases, entries, _inliner) = P0._compile_suite(suite)
        vm = PaintVM(
            heap=heap.clone(), directory=directory,
            macro_symbols=P0._macro_symbol_objs(heap, entry_flags, resident_flags),
            max_steps=100_000, max_call_args=12,
            abi_profile="dialect-v2", abi_ledger=P0._suite_abi(suite)[1],
        )
        result = vm.run(directory[heap.intern(entries[0])], [])
        require(vm.heap.obj_to_text(result) == compiled_cases[0]["expect"],
                "paint trace result drift")
        return vm.paint_calls
    finally:
        path.unlink()


def _walk_calls(form: Any, caller: str, found: list[tuple[str, str, Any]]) -> None:
    if not isinstance(form, list) or not form:
        return
    head = form[0]
    if isinstance(head, str) and head in PASS_NAMES | {"%sexp-paint"}:
        found.append((caller, head, form[-1] if len(form) > 1 else None))
    for item in form:
        _walk_calls(item, caller, found)


def caller_audit(extra_source: str = "") -> dict[str, Any]:
    calls: list[tuple[str, str, Any]] = []
    paths = sorted((ROOT / "lib").glob("*.lisp"))
    for path in paths:
        for form in C.parse_all(path.read_text(encoding="utf-8")):
            if isinstance(form, list) and len(form) >= 4 and form[0] == "defun":
                for body in form[3:]:
                    _walk_calls(body, str(form[1]), calls)
    for form in C.parse_all(extra_source):
        if isinstance(form, list) and len(form) >= 4 and form[0] == "defun":
            for body in form[3:]:
                _walk_calls(body, str(form[1]), calls)
    external = []
    for caller, target, edge in calls:
        if caller == target:
            continue
        external.append({"caller": caller, "target": target, "edge": edge})
        if target in PASS_NAMES:
            require(caller in PAINT_OWNERS and edge == "nil",
                    f"unbounded or foreign matcher caller: {caller}->{target} edge={edge!r}")
        else:
            require(caller in PAINT_OWNERS and edge == 0,
                    f"foreign paint owner: {caller}->{target} phase={edge!r}")
    return {"all_calls": len(calls), "external_calls": external,
            "activation": "deferred" if not external else "surface-owned"}


def suite_ownership() -> dict[str, Any]:
    resident = P0._apply_suite_transforms(P0._read_suite(WORKBENCH_SUITE))
    ide = P0._apply_suite_transforms(P0._read_suite(IDE_SUITE))
    require("lib/sexp-depth.lisp" in resident.get("sources", []),
            "resident matcher source absent")
    require(all(name in resident.get("functions", []) for name in FUNCTIONS),
            "resident matcher function absent")
    require(all(name not in ide.get("functions", []) for name in FUNCTIONS),
            "IDE emits a second matcher owner")
    require("../stdlib/p0-stdlib-einsuite-core-workbench-subset.json"
            in ide.get("resident_suites", []), "IDE resident matcher authority absent")
    product_code = P0._compile_suite(resident, include_cases=False)[2]
    product_sizes = {name: len(product_code[name].encode()) for name in FUNCTIONS}
    return {
        "source": "lib/sexp-depth.lisp",
        "resident_owner": WORKBENCH_SUITE.relative_to(ROOT).as_posix(),
        "resident_functions": list(FUNCTIONS),
        "product_emitted_function_bytes": product_sizes,
        "ide_emitted_duplicates": [],
        "ide_consumes_resident_owner": True,
    }


def mutation_caught(name: str, action: Any) -> dict[str, Any]:
    try:
        action()
    except Exception as exc:  # expected rejection is the evidence
        return {"name": name, "caught": True, "diagnostic": str(exc)[:240]}
    raise CardError(f"mutation survived: {name}")


def mutations(source: str) -> list[dict[str, Any]]:
    rows = []
    rows.append(mutation_caught(
        "escaped-quote-state-removed",
        lambda: compile_core(source.replace("(if (= state 3)", "(if (= state 0)", 1))))
    rows.append(mutation_caught(
        "comment-delimiter-changed",
        lambda: compile_core(source.replace("(if (= c 59)", "(if (= c 58)", 1))))
    for target, marker in [
        ("scan-four-code-chunk", "%sexp-scan source codes stop i packed"),
        ("close-four-code-chunk", "%sexp-close source codes stop i packed kind"),
        ("open-four-code-chunk", "%sexp-open source codes stop i combined target kind"),
    ]:
        start = source.index(marker)
        end = source.find("\n(defun ", start)
        if end < 0:
            end = len(source)
        body = source[start:end]
        require(body.count("(+ i 3)") == 2, f"{target}: chunk clamp shape drift")
        mutant = source[:start] + body.replace("(+ i 3)", "(+ i 4)") + source[end:]
        rows.append(mutation_caught(target, lambda mutant=mutant: compile_core(mutant)))
    rows.append(mutation_caught(
        "cursor-loses-composed-paint",
        lambda: require(
            paint_trace(source.replace("(if (= index cursor) 129", "(if (= index cursor) 7", 1))
            == [(0, 4, 40, 1), (2, 4, 41, 1), (3, 4, 40, 129), (5, 4, 41, 7)],
            "cursor no longer wins composed paint")))
    rows.append(mutation_caught(
        "stale-highlight-not-restored",
        lambda: require(
            paint_trace(source.replace("(if (< phase 2) 1 7)", "(if (< phase 2) 7 7)", 1))
            == [(0, 4, 40, 1), (2, 4, 41, 1), (3, 4, 40, 129), (5, 4, 41, 7)],
            "old highlight was not restored")))
    rows.append(mutation_caught(
        "foreign-unbounded-pass-caller",
        lambda: caller_audit("(defun %foreign (s) (%sexp-scan s nil 250 0 0 4))")))
    rows.append(mutation_caught(
        "foreign-paint-owner",
        lambda: caller_audit("(defun %foreign (s) (%sexp-paint s nil nil 0 0 80 0 0))")))
    return rows


def build_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    pricing = load(PRICING)
    require(contract.get("format") ==
            "lisp65-c2-v17-sexp-scanner-paint-card-contract-v1",
            "card contract format drift")
    source = SOURCE.read_text(encoding="utf-8")
    compiled = compile_core(source)
    limits = contract["limits"]
    require(compiled["maximum_object_bytes"] < limits["max_code_object_bytes"],
            "matcher object reaches 255-byte ceiling")
    require(compiled["total_function_bytes"] <=
            limits["conservative_block3_bank2_ceiling"],
            "card-1 exact freight exceeds priced Block-3 envelope")
    allocating = {"cons", "list", "append", "reverse", "string->list", "list->string"}
    require(not (allocating & set(compiled["runtime_call_targets"])),
            "matcher or painter body contains an allocating call")
    semantic_rows = [row for row in compiled["cases"] if row["class"] != "paint"]
    require(all(row["runtime_allocations"] == 0 for row in semantic_rows),
            "matcher hot path allocated")
    expected_trace = [
        (0, 4, 40, 1), (2, 4, 41, 1),
        (3, 4, 40, 129), (5, 4, 41, 7),
    ]
    trace = paint_trace(source)
    require(trace == expected_trace, f"composed paint trace drift: {trace!r}")
    owner = suite_ownership()
    require(owner["product_emitted_function_bytes"] == compiled["function_bytes"],
            "isolated and product-profile emitted object sizes differ")
    callers = caller_audit()
    require(callers["activation"] == "deferred",
            "card 1 activated an idle surface prematurely")
    before = pricing["delivery_world"]["free_before"]
    minimum = pricing["delivery_world"]["minimum_free"]
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in FUNCTIONS)
    after = {"symbol_slots": before["symbol_slots"] - len(FUNCTIONS),
             "namepool_bytes": before["namepool_bytes"] - name_bytes}
    margin = {"symbol_slots": after["symbol_slots"] - minimum["symbol_slots"],
              "namepool_bytes": after["namepool_bytes"] - minimum["namepool_bytes"]}
    require(margin["symbol_slots"] >= 0 and margin["namepool_bytes"] >= 0,
            "card-1 name freight crosses release floor")
    mutation_rows = mutations(source)
    require(all(row["caught"] for row in mutation_rows), "mutation set incomplete")
    metadata = load(METADATA_INDEX)
    metadata_names = {row["name"] for row in metadata.get("records", [])}
    require(not (set(FUNCTIONS) & metadata_names),
            "private matcher freight leaked into public function metadata")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-26",
        "status": "passed-host-card-1-scanner-paint-inactive-until-idle-cards",
        "inputs": [
            bind(CONTRACT), bind(PRICING), bind(SOURCE), bind(IDE_SYNTAX),
            bind(SHIP_INPUT_SUITE), bind(CORE_SUITE), bind(LEGACY_CORE_SUITE),
            bind(LEGACY_STDLIB_SUITE), bind(LEGACY_WORKBENCH_SUITE),
            bind(COMFORT_DELTA_SUITE), bind(M65_SUITE),
            bind(STDLIB_SUITE), bind(FASL_SUITE), bind(WORKBENCH_SUITE), bind(IDE_SUITE),
            bind(METADATA_INDEX), bind(METADATA_RECEIPT),
        ],
        "emitted_core": compiled,
        "exact_bank2_function_bytes": compiled["total_function_bytes"],
        "maximum_object_bytes": compiled["maximum_object_bytes"],
        "conservative_1684_byte_envelope_replaced_for_card1": True,
        "capacity": {
            "free_before": before, "card1_names": list(FUNCTIONS),
            "card1_name_bytes": name_bytes, "free_after_card1": after,
            "minimum_free": minimum, "margin_after_card1": margin,
            "measurement": pricing["delivery_world"]["measurement"],
        },
        "chunk_contract": {
            "codes_per_invocation": 3,
            "self_enforced_edge": "min(stop,i+3)",
            "external_edge": "nil only",
            "scan_open_close_all_covered": True,
            "timing_claim": "host instruction counts only; no device frame claim",
        },
        "paint_ownership": {
            "expected_trace": [list(row) for row in expected_trace],
            "observed_trace": [list(row) for row in trace],
            "trace_fields": ["column", "row", "code", "attribute"],
            "old_pair_restored_before_new_pair": True,
            "cursor_wins_composition": True,
            "surface_activation": callers["activation"],
        },
        "single_owner": owner,
        "public_metadata": {
            "records": len(metadata_names),
            "private_matcher_entries": [],
            "successor_index_candidate_derived": True,
        },
        "caller_audit": callers,
        "mutations": mutation_rows,
        "claim_limit": (
            "Host-only card 1. Ships the resident shared matcher core and composed "
            "paint transition, but activates neither surface and claims no blink, "
            "current device timing, product link, medium or hardware acceptance."
        ),
        "next": "review card 1; then line-editor idle/blink card",
    }


def check_sealed_receipt() -> dict[str, Any]:
    """Keep card 1 in its reviewed world while checking live successors.

    Card 2 deliberately activates ``%rl-idle`` and changes the line suite.
    Re-deriving card 1 would rewrite its reviewed ``activation=deferred``
    witness.  The receipt therefore remains byte-identical to its sealing
    commit; the enduring scanner, ownership and mutation claims are checked
    afresh below against the live successor.
    """
    require(RECEIPT.is_file() and not RECEIPT.is_symlink(),
            "scanner/paint receipt absent")
    raw = RECEIPT.read_bytes()
    require(raw == ERA.era_blob(
        SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
        "sealed scanner/paint receipt was rewritten")
    value = json.loads(raw)
    require(value.get("format") == FORMAT
            and value.get("exact_bank2_function_bytes") == 996
            and value.get("maximum_object_bytes") == 218,
            "sealed scanner/paint identity drift")
    return value


def check_live_successor() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    compiled = compile_core(source)
    require(compiled["total_function_bytes"] == 996
            and compiled["maximum_object_bytes"] == 218,
            "live successor changed the accepted shared core")
    owner = suite_ownership()
    require(owner["product_emitted_function_bytes"] == compiled["function_bytes"],
            "live successor duplicated or changed shared matcher emission")
    callers = caller_audit()
    require(callers["activation"] == "surface-owned",
            "reviewed successors did not retain surface-owned activation")
    observed = {(row["caller"], row["target"], row["edge"])
                for row in callers["external_calls"]}
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
    require(observed == expected,
            f"live successor matcher ownership drift: {sorted(observed)!r}")
    mutation_rows = mutations(source)
    require(all(row["caught"] for row in mutation_rows),
            "live successor weakened a card-1 mutation")
    return {"caller_audit": callers, "mutations": mutation_rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.write:
            raise CardError("card-1 receipt is sealed; successor cards may not rewrite it")
        receipt = check_sealed_receipt()
        live = check_live_successor()
        print("v1.7 scanner/paint card: PASS "
              f"bytes={receipt['exact_bank2_function_bytes']} "
              f"max_object={receipt['maximum_object_bytes']} "
              f"free={receipt['capacity']['free_after_card1']['symbol_slots']}/"
              f"{receipt['capacity']['free_after_card1']['namepool_bytes']} "
              f"live_callers={len(live['caller_audit']['external_calls'])} "
              f"mutations={len(live['mutations'])}")
        return 0
    except (CardError, PRICE.PricingError, P0.StdlibCheckError,
            C.CompileError, VM.VMError) as exc:
        print(f"v1.7 scanner/paint card: FIRST RED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
