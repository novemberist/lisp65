#!/usr/bin/env python3
"""Prove and price the recursive REPL direct-expression successor.

The historical F1 gate admitted published calls whose arguments were already
literal values.  This successor keeps that domain and admits a recursively
closed expression tree: bound variable reads and nested published bytecode
calls.  Persistent and special forms retain the exact compiler/install lane.

The executable proof rebuilds only the product stdlib plane in a temporary
directory, loads the accepted Link-96 compiler carrier, and runs the real
``lcc-run``.  No product link or target contact is performed.
"""

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


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_repl_pipeline_cost_attribution as PIPE  # noqa: E402
import c2_top_level_macro_redispatch as REDISPATCH  # noqa: E402


CONTRACT = ROOT / "config/c2-repl-direct-expression-contract.json"
SOURCE = ROOT / "lib/dialect-v2/eval-runtime.lisp"
BASE_MANIFEST = ROOT / (
    "build/c2.3/link95-packed-callee-closure/static-plane/narrow-static/"
    "stdlib-p0.manifest.json"
)
BASE_SUITE = ROOT / (
    "build/c2.3/link95-packed-callee-closure/"
    "link95-closed-stdlib-suite.json"
)
LINK96_CANONICAL = ROOT / (
    "build/c2.3/terminal-return-guard-link96/canonical-product-manifest.json"
)
BASE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link96-repl-pipeline-cost-attribution-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-repl-direct-expression-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
PRODUCT_RUNTIME = ROOT / "src/c2_product_runtime.c"
EVAL_SOURCE = ROOT / "src/eval.c"
LEGACY_INSTALLER = ROOT / "src/lcc_install_overlay.c"
DYNAMIC_GAP = ROOT / "config/c2-dynamic-code-gap-proposal.json"
EXPERIENCE_PLAN = ROOT / "docs/planning/startup-require-experience-work-plan.md"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-repl-direct-expression-v1"
OLD_EVAL_SOURCE = (
    "build/c2.3/link95-packed-callee-closure/codemod/sources/"
    "lib/dialect-v2/eval-runtime.lisp"
)
PUBLISHED_MACRO_HELPER = "%c2-top-level-macro-p"
NEW_HELPERS = ("%c2-direct-expression-p", "%c2-direct-expression")
EXPERIENCE_BASE_COMMIT = "236eba09f55d396e62090a379821df91b81ab8ee"
DIRECT_DEFS = (
    "%c2-direct-quoted-value-p",
    "%c2-direct-value-p",
    "%c2-direct-values-p",
    "%c2-direct-value",
    "%c2-direct-expression-p",
    "%c2-direct-expression",
    "%c2-direct-values",
    "%c2-published-direct-call-p",
    "%c2-top-level-expand",
    "%c2-top-level-run-forms",
    "%c2-run-expanded",
    "lcc-run",
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def selected_defs(source: str) -> dict[str, Any]:
    forms = {
        form[1]: form
        for form in C.parse_all(source)
        if isinstance(form, list) and len(form) >= 4 and form[0] == "defun"
    }
    require(all(name in forms for name in DIRECT_DEFS),
            "direct-expression helper inventory incomplete")
    return {name: forms[name] for name in DIRECT_DEFS}


def validate_contract(contract: dict[str, Any], source: str) -> dict[str, Any]:
    require(contract["format"] == "lisp65-c2-repl-direct-expression-contract-v1",
            "contract identity drift")
    direct = contract["direct_domain"]
    wall = contract["fallback_wall"]
    accounting = contract["accounting"]
    require(
        direct["operator"] == "published bytecode function cell"
        and direct["evaluation_order"] == "left-to-right"
        and direct["transaction_effect"] == "none"
        and "bound variable read" in direct["arguments_recursive"]
        and "another admitted published bytecode call"
            in direct["arguments_recursive"],
        "direct recursive domain drift",
    )
    require(
        "Every form which can publish a definition reaches lcc-install"
            in wall["persistent_rule"]
        and accounting == {
            "resident_bytes": 0,
            "transaction_state_bytes": 0,
            "new_roots": 0,
            "placement": "Bank-2 product runtime",
            "product_link_authorized": False,
            "hardware_claim": False,
            "release_claim": False,
        },
        "fallback/accounting wall drift",
    )
    forms = selected_defs(source)
    expression_p = forms["%c2-direct-expression-p"]
    expression = forms["%c2-direct-expression"]
    values_p = forms["%c2-direct-values-p"]
    run = forms["%c2-run-expanded"]
    require("boundp" in repr(expression_p)
            and "%c2-published-direct-call-p" in repr(expression_p),
            "recursive predicate lost bound/call closure")
    require("symbol-value" in repr(expression)
            and "%c2-direct-values" in repr(expression),
            "recursive evaluator lost bound/call closure")
    require(
        "(funcall (car form))" in source
        and "(apply (car form) (%c2-direct-values (cdr form)))" in source,
        "recursive evaluator dispatch drifted",
    )
    require("%c2-direct-expression-p" in repr(values_p),
            "argument walker is not recursively closed")
    require("%c2-compile-form" in repr(run) and "lcc-install" in repr(run),
            "historical compiler/install fallback absent")
    require(
        all(fragment in source for fragment in (
            "(let ((compiled (%c2-compile-form form)))",
            "(%set-macro (car (cdr form)) (lcc-install compiled nil))",
            "(lcc-install compiled (car (cdr form)))",
            "(t (lcc-install compiled 't))",
        )),
        "definition/expression install branches drifted",
    )
    return {"definitions": list(forms), "fallback_preserved": True}


def candidate_runtime_source() -> str:
    runtime = REDISPATCH.candidate_runtime(load(REDISPATCH.CONTRACT))
    require(
        "(%c2-top-level-macro-p (car form))" in runtime
        and "(defun %c2-top-level-macro-p (op)" in runtime
        and "(%lcc-macro-p (car form))" not in runtime,
        "Link-95 published macro-predicate successor drift",
    )
    return runtime


def candidate_suite(
    runtime_path: Path, *, require_path: Path | None = None,
) -> dict[str, Any]:
    suite = STD._read_suite(str(BASE_SUITE))
    require(OLD_EVAL_SOURCE in suite["sources"], "baseline eval source absent")
    suite["sources"] = [
        str(runtime_path) if item == OLD_EVAL_SOURCE else item
        for item in suite["sources"]
    ]
    if require_path is not None:
        require("lib/stdlib-require.lisp" in suite["sources"],
                "live require source absent from candidate suite")
        suite["sources"] = [
            str(require_path) if item == "lib/stdlib-require.lisp" else item
            for item in suite["sources"]
        ]
    require(PUBLISHED_MACRO_HELPER in suite["functions"],
            "Link-95 published macro helper absent")
    position = suite["functions"].index(PUBLISHED_MACRO_HELPER) + 1
    for name in reversed(NEW_HELPERS):
        suite["functions"].insert(position, name)
    return suite


def validate_candidate_publication(manifest: dict[str, Any]) -> None:
    entries = {row["name"]: row for row in manifest["entries"]}
    require(
        PUBLISHED_MACRO_HELPER in entries
        and not entries[PUBLISHED_MACRO_HELPER].get("anonymous", False)
        and PUBLISHED_MACRO_HELPER
            in repr(entries["%c2-top-level-expand"].get("literals", []))
        and "%lcc-macro-p"
            not in repr(entries["%c2-top-level-expand"].get("literals", [])),
        "candidate replay masked the Link-95 publication boundary",
    )


def emit_candidate(prefix: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    runtime = candidate_runtime_source()
    runtime_path = prefix.parent / "eval-runtime.lisp"
    runtime_path.write_text(runtime, encoding="utf-8")
    # This permanent gate prices only the accepted direct-expression change.
    # Later Experience work may legitimately change another suite member
    # (notably require); bind that input to the commit which accepted this gate
    # so unrelated freight cannot contaminate its accounting.
    require_path = prefix.parent / "stdlib-require.direct-authority.lisp"
    require_path.write_bytes(subprocess.run(
        ["git", "show", f"{EXPERIENCE_BASE_COMMIT}:lib/stdlib-require.lisp"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout)
    emitted = STD.emit_artifacts(
        str(BASE_SUITE),
        candidate_suite(runtime_path, require_path=require_path), str(prefix),
        artifact_role="stdlib",
    )
    manifest = load(Path(emitted["manifest"]))
    validate_candidate_publication(manifest)
    return emitted, manifest, runtime


def add_definition(
    text: str, heap: B.Heap, directory: dict[int, B.CodeObject],
    names: dict[int, str], origins: dict[int, str], macros: set[int],
    ledger: dict[str, Any], *, macro: bool = False,
) -> None:
    form = C.parse_one(text)
    name, code, helpers = C.compile_top_form_with_helpers(
        form, heap, strict_arity=True,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    require(name is not None and not helpers,
            f"fixture emitted helpers: {name}")
    symbol = heap.intern(name)
    directory[symbol] = code
    names[id(code)] = name
    origins[id(code)] = "proof-fixture"
    if macro:
        macros.add(symbol)


class GateVM(PIPE.PipelineVM):
    """Add the target's one-step macroexpand primitive to the P0 replay."""

    def _callprim(
        self, prim_id: int, argc: int, stack: list[int], pc: int | None = None,
        native_base: int = 0, frame_slots: int = 0,
    ) -> int:
        if prim_id == 39:
            self._check_argc(argc, "CALLPRIM")
            require(argc == 1 and len(stack) >= 1,
                    "macroexpand-1 ABI drift")
            args = self._pop_args(argc, stack)
            form = args[0]
            require(self.heap.consp(form), "macroexpand-1 form is not a call")
            operation = self.heap.car(form)
            macro_args = self._list_to_objs(
                self.heap.cdr(form), "macroexpand-1"
            )
            self._trace_call(
                "CALLPRIM", "macroexpand-1", argc, pc=pc, resolved=True
            )
            return self._invoke_function(
                operation, macro_args,
                native_base=native_base + frame_slots + len(stack),
            )
        return super()._callprim(
            prim_id, argc, stack, pc=pc,
            native_base=native_base, frame_slots=frame_slots,
        )


def runtime(candidate_manifest: Path) -> tuple[Any, ...]:
    canonical_value, _old_stdlib, carrier_path = PIPE.manifest_paths(
        LINK96_CANONICAL
    )
    heap = C.prepare_heap([])
    directory: dict[int, B.CodeObject] = {}
    macros: set[int] = set()
    names: dict[int, str] = {}
    origins: dict[int, str] = {}
    candidate = PIPE.load_manifest_entries(
        heap, candidate_manifest, "candidate-runtime",
        directory, macros, names, origins,
    )
    carrier = PIPE.load_manifest_entries(
        heap, carrier_path, "compiler-carrier",
        directory, macros, names, origins,
    )
    ledger = load(ROOT / "config/bytecode-abi-ledger.json")
    fixtures = (
        "(defun probe (x) x)",
        "(defun point-y (point) (car (cdr (cdr point))))",
        "(defun %order-add (n) "
        "  (set-symbol-value 'order (+ (symbol-value 'order) n)))",
    )
    for fixture in fixtures:
        add_definition(
            fixture, heap, directory, names, origins, macros, ledger
        )
    add_definition(
        "(defun %make-proof-function (name) "
        "  '(defun %proof-made nil 7))",
        heap, directory, names, origins, macros, ledger, macro=True,
    )
    return (
        canonical_value, candidate, carrier, heap, directory,
        macros, names, origins, ledger,
    )


def run_case(state: tuple[Any, ...], source: str,
             bindings: dict[str, int] | None = None) -> dict[str, Any]:
    (_canonical, _candidate, _carrier, heap, directory,
     macros, names, origins, ledger) = state
    for name, value in (bindings or {}).items():
        heap.set_symbol_value(heap.intern(name), value)
    parsed = C.parse_one(source)
    trace = PIPE.PipelineTrace(origins)
    vm = GateVM(
        heap=heap, directory=directory, macro_symbols=macros,
        max_steps=10_000_000, trace=trace, code_names=names,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    form = vm._compiler_form_obj(parsed)
    try:
        result = vm.run(directory[heap.intern("lcc-run")], [form])
    except PIPE.InstallBoundary as boundary:
        return {
            "route": "compile-install",
            "install_calls": trace.install_calls,
            "install_name": heap.obj_to_text(boundary.args[1]),
            "instructions": vm.steps,
        }
    except B.VMError as error:
        return {
            "route": "vm-error", "error": error.status,
            "detail": str(error),
            "functions": trace.summary()["instructions_by_function"],
            "install_calls": trace.install_calls, "instructions": vm.steps,
        }
    return {
        "route": "direct", "result": heap.obj_to_text(result),
        "install_calls": trace.install_calls, "instructions": vm.steps,
    }


def executable_proof(candidate_manifest: Path) -> dict[str, Any]:
    state = runtime(candidate_manifest)
    heap: B.Heap = state[3]
    lst = heap.list_from_py([1, 2, 3])
    point = heap.list_from_py([heap.intern("point"), 3, 4])
    direct_cases = (
        ("historical-flat", "(probe 41)", {}, "41"),
        ("nested-call", "(+ 1 (+ 2 3))", {}, "6"),
        ("bound-list-access", "(car (cdr lst))", {"lst": lst}, "2"),
        ("accessor", "(point-y test)", {"test": point}, "4"),
        ("allocation", "(list 1 2 3 4 5)", {}, "(1 2 3 4 5)"),
    )
    direct_rows: list[dict[str, Any]] = []
    for name, source, bindings, expected in direct_cases:
        row = run_case(state, source, bindings)
        require(row["route"] == "direct" and row["result"] == expected
                and row["install_calls"] == 0,
                f"direct fixture red: {name}: {row}")
        direct_rows.append({"case": name, "source": source, **row})

    heap.set_symbol_value(heap.intern("order"), B.mkfix(0))
    ordered = run_case(state, "(list (%order-add 1) (%order-add 10))")
    require(ordered["route"] == "direct"
            and ordered["result"] == "(1 11)"
            and B.fixval(heap.symbol_value(heap.intern("order"))) == 11,
            f"left-to-right proof red: {ordered}")

    fallback_cases = (
        ("setq", "(setq x 1)", "t"),
        ("definition", "(defun %proof-new () 7)", "%proof-new"),
        ("macro-definition", "(defmacro %proof-m () 7)", "nil"),
        ("macro-generated-definition", "(%make-proof-function %proof-made)",
         "%proof-made"),
        ("special-form", "(if t 1 2)", "t"),
        ("unbound-value", "(probe never-bound)", "t"),
    )
    fallback_rows: list[dict[str, Any]] = []
    for name, source, install_name in fallback_cases:
        row = run_case(state, source)
        require(row["route"] == "compile-install"
                and row["install_calls"] == 1
                and row["install_name"] == install_name,
                f"fallback wall red: {name}: {row}")
        fallback_rows.append({"case": name, "source": source, **row})

    undefined = run_case(state, "(%proof-undefined 1)")
    require(undefined["route"] == "compile-install"
            and undefined["install_calls"] == 1,
            f"undefined callee entered direct path: {undefined}")
    wrong_arity = run_case(state, "(probe 1 2)")
    require(wrong_arity["route"] == "vm-error"
            and wrong_arity["error"] == "ArityError"
            and wrong_arity["install_calls"] == 0,
            f"VM arity authority red: {wrong_arity}")
    return {
        "direct": direct_rows,
        "left_to_right": ordered,
        "fallback": fallback_rows,
        "undefined": undefined,
        "wrong_arity": wrong_arity,
        "direct_cases": len(direct_rows) + 1,
        "fallback_cases": len(fallback_rows) + 2,
    }


def mutation_tests(contract: dict[str, Any], source: str) -> int:
    mutations: list[tuple[dict[str, Any], str]] = []
    for old, new in (
        ("(boundp form)", "t"),
        ("(%c2-published-direct-call-p form)", "t"),
        ("(%c2-direct-expression-p (car forms))", "t"),
        ("(symbol-value form)", "form"),
        ("(%c2-compile-form form)", "form"),
        ("(lcc-install compiled (car (cdr form)))", "compiled"),
    ):
        require(old in source, f"mutation anchor absent: {old}")
        mutations.append((copy.deepcopy(contract), source.replace(old, new, 1)))
    bad = copy.deepcopy(contract)
    bad["accounting"]["resident_bytes"] = 1
    mutations.append((bad, source))
    bad = copy.deepcopy(contract)
    bad["direct_domain"]["evaluation_order"] = "unspecified"
    mutations.append((bad, source))
    bad = copy.deepcopy(contract)
    bad["fallback_wall"]["persistent_rule"] = "best effort"
    mutations.append((bad, source))
    for index, (item_contract, item_source) in enumerate(mutations):
        try:
            validate_contract(item_contract, item_source)
        except (GateError, C.CompileError):
            continue
        raise GateError(f"mutation accepted: {index}")
    publication = {
        "entries": [
            {"name": PUBLISHED_MACRO_HELPER, "anonymous": False},
            {
                "name": "%c2-top-level-expand",
                "literals": [{"symbol": PUBLISHED_MACRO_HELPER}],
            },
        ],
    }
    validate_candidate_publication(publication)
    publication_mutations = []
    bad = copy.deepcopy(publication)
    bad["entries"][0]["anonymous"] = True
    publication_mutations.append(bad)
    bad = copy.deepcopy(publication)
    bad["entries"][1]["literals"] = [{"symbol": "%lcc-macro-p"}]
    publication_mutations.append(bad)
    for index, bad in enumerate(publication_mutations, start=len(mutations)):
        try:
            validate_candidate_publication(bad)
        except GateError:
            continue
        raise GateError(f"publication mutation accepted: {index}")
    return len(mutations) + len(publication_mutations)


def amortisation_audit() -> dict[str, Any]:
    runtime = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    evaluator = EVAL_SOURCE.read_text(encoding="utf-8")
    legacy = LEGACY_INSTALLER.read_text(encoding="utf-8")
    gap = load(DYNAMIC_GAP)
    plan = EXPERIENCE_PLAN.read_text(encoding="utf-8")
    require(
        all(row in runtime for row in (
            "obj c2_product_install(obj fnlist, obj definition_name)",
            "emit = c2_session_emit_reset();",
            "append_ok = c2_append_begin(length, &before, &main",
            "result = vm_run_dir((int)main, 0, 0);",
            "if (!c2_append_rollback(&before))",
        )),
        "C2 transient ceremony projection drift",
    )
    require(
        "#if defined(LISP65_C2_PRODUCT_CUT)" in evaluator
        and "#elif defined(LISP65_LCC_INSTALL)" in evaluator
        and "lcc_install_overlay(fnlist, defname" in evaluator,
        "product/legacy installer exclusivity drift",
    )
    require(
        "lcc_install_transient_pop" in legacy
        and any(
            row["id"] == "mutable-session-code-lane"
            and row["assessment"]
                == "fallback-needs-address-and-root-contract-amendment"
            for row in gap["options"]
        )
        and any(
            row["id"] == "legacy-l65m-transition-lane"
            and row["assessment"] == "rejected"
            for row in gap["options"]
        ),
        "rejected alternate execution-lane authority drift",
    )
    require(
        "An honest \"no material lever\" is a\nvalid exit." in plan
        and "without\nweakening publication or rollback" in plan,
        "Phase-C bounds drift",
    )
    return {
        "authorities": {
            "product_runtime": bind(PRODUCT_RUNTIME),
            "product_dispatch": bind(EVAL_SOURCE),
            "legacy_installer": bind(LEGACY_INSTALLER),
            "dynamic_code_gap": bind(DYNAMIC_GAP),
            "experience_plan": bind(EXPERIENCE_PLAN),
        },
        "current_product_lane": (
            "emit -> authenticated append -> execute -> rollback; serial and "
            "repeated once for every non-direct expression"
        ),
        "priced_candidates": [
            {
                "candidate": "reuse the legacy transient overlay",
                "result": "rejected",
                "reason": (
                    "compile-time-exclusive non-C2 implementation; restoring it "
                    "would reintroduce the rejected dual decoder/address domain"
                ),
            },
            {
                "candidate": "mutable reusable C2 execution slot",
                "result": "out-of-scope architecture",
                "reason": (
                    "requires a new address, literal-root, generation and "
                    "publication contract; no such owned lane exists"
                ),
            },
            {
                "candidate": "skip append or rollback for compiled expressions",
                "result": "rejected",
                "reason": (
                    "weakens the immutable-code and rollback contracts which are "
                    "explicit Phase-C walls"
                ),
            },
            {
                "candidate": "batch independent interactive forms",
                "result": "not a single-form latency lever",
                "reason": (
                    "changes prompt/RETURN semantics and cannot reduce the first "
                    "form's 60/62-frame response"
                ),
            },
        ],
        "conclusion": (
            "No in-scope ceremony-amortisation lever survives the current one-"
            "decoder, immutable-publication and rollback walls.  The recursive "
            "direct path is the material safe result; setq and definitions retain "
            "the measured 60/62-frame lane."
        ),
        "release_edge": (
            "still red for ceremony forms: sub-0.5-second response requires a "
            "separately owned transient-execution architecture, not a local edit"
        ),
    }


def core_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    source = SOURCE.read_text(encoding="utf-8")
    source_gate = validate_contract(contract, source)
    source_gate["mutations_rejected"] = mutation_tests(contract, source)
    baseline = load(BASE_MANIFEST)
    prior = load(BASE_RECEIPT)
    require(prior["stage_prices"]["transient_install_execute_rollback"]
            ["derived_whole_envelope_frames_cold_warm"] == [60, 62],
            "60/62-frame baseline drift")
    with tempfile.TemporaryDirectory(prefix="lisp65-repl-direct-") as directory:
        emitted, candidate, candidate_runtime = emit_candidate(
            Path(directory) / "stdlib-p0"
        )
        proof = executable_proof(Path(emitted["manifest"]))
    accounting = {
        "objects_before": baseline["objects"],
        "objects_after": candidate["objects"],
        "objects_delta": candidate["objects"] - baseline["objects"],
        "code_bytes_before": baseline["code_bytes"],
        "code_bytes_after": candidate["code_bytes"],
        "code_bytes_delta": candidate["code_bytes"] - baseline["code_bytes"],
        "external_bytes_before": baseline["external_image"]["bytes"],
        "external_bytes_after": candidate["external_image"]["bytes"],
        "external_bytes_delta": (
            candidate["external_image"]["bytes"]
            - baseline["external_image"]["bytes"]
        ),
        "directory_bytes_before": baseline["directory_bytes"],
        "directory_bytes_after": candidate["directory_bytes"],
        "directory_bytes_delta": (
            candidate["directory_bytes"] - baseline["directory_bytes"]
        ),
        "resident_bytes_delta": 0,
    }
    require(accounting == {
        "objects_before": 391, "objects_after": 393, "objects_delta": 2,
        "code_bytes_before": 17134, "code_bytes_after": 17206,
        "code_bytes_delta": 72,
        "external_bytes_before": 40126, "external_bytes_after": 40340,
        "external_bytes_delta": 214,
        "directory_bytes_before": 2737, "directory_bytes_after": 2751,
        "directory_bytes_delta": 14, "resident_bytes_delta": 0,
    }, f"candidate accounting drift: {accounting}")
    gate_text = GATES.read_text(encoding="utf-8")
    wiring = [
        "c2-repl-direct-expression-selftest:",
        "python3 tools/host-lisp/c2_repl_direct_expression_gate.py selftest",
        "c2-repl-direct-expression-check:",
        "python3 tools/host-lisp/c2_repl_direct_expression_gate.py check",
        "check-source: c2-repl-direct-expression-check",
    ]
    require(all(row in gate_text for row in wiring), "gate wiring absent")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": "PASSED-DIRECT-EXPRESSION-WIDENING-HOST-AND-ARTIFACT-GATES",
        "scope": {
            "product_links": 0, "device_contacts": 0,
            "resident_bytes_delta": 0, "release_claim": False,
        },
        "authorities": {
            "contract": bind(CONTRACT), "source": bind(SOURCE),
            "baseline_manifest": bind(BASE_MANIFEST),
            "baseline_attribution": bind(BASE_RECEIPT),
            "Link96_world": bind(LINK96_CANONICAL),
            "driver": bind(DRIVER),
        },
        "source_gate": source_gate,
        "candidate_runtime": {
            "bytes": len(candidate_runtime.encode("utf-8")),
            "sha256": sha(candidate_runtime.encode("utf-8")),
            "published_macro_predicate": PUBLISHED_MACRO_HELPER,
            "compiler_private_macro_predicate_absent": True,
        },
        "execution": proof,
        "accounting": accounting,
        "ceremony_amortisation": amortisation_audit(),
        "effect": {
            "common_nested_calls": "60/62-frame ceremony removed",
            "bound_accessor_calls": "60/62-frame ceremony removed",
            "persistent_and_special_forms": "unchanged compile/install ceremony",
            "remaining_target": (
                "amortise the measured ceremony without weakening publication "
                "or rollback; no sub-0.5-second claim is made by this host gate"
            ),
        },
        "gate_wiring": wiring,
    }


def selftest() -> dict[str, Any]:
    contract = load(CONTRACT)
    source = SOURCE.read_text(encoding="utf-8")
    validate_contract(contract, source)
    return {"status": "passed", "mutations": mutation_tests(contract, source)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.mode == "selftest":
            print(json.dumps(selftest(), indent=2, sort_keys=True))
            return 0
        value = core_receipt()
        if args.mode == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
        else:
            historical = load(RECEIPT)
            historical_runtime = historical["ceremony_amortisation"][
                "authorities"]["product_runtime"]
            current_runtime = value["ceremony_amortisation"][
                "authorities"]["product_runtime"]
            require(historical_runtime["path"] == current_runtime["path"],
                    "REPL direct-expression runtime authority changed identity")
            # amortisation_audit() has just re-run every relevant current-source
            # assertion.  Preserve the historical receipt while comparing the
            # semantic result, not unrelated bytes in the shared runtime file.
            historical_runtime.clear()
            historical_runtime["path"] = current_runtime["path"]
            current_runtime.clear()
            current_runtime["path"] = historical_runtime["path"]
            historical_driver = historical["authorities"]["driver"]
            current_driver = value["authorities"]["driver"]
            require(historical_driver["path"] == current_driver["path"],
                    "REPL direct-expression checker identity drift")
            historical_driver.clear()
            historical_driver["path"] = current_driver["path"]
            current_driver.clear()
            current_driver["path"] = historical_driver["path"]
            require(historical == value,
                    "REPL direct-expression semantic receipt drift")
        print(json.dumps({
            "status": value["status"],
            "direct_cases": value["execution"]["direct_cases"],
            "fallback_cases": value["execution"]["fallback_cases"],
            "mutations": value["source_gate"]["mutations_rejected"],
            "code_bytes_delta": value["accounting"]["code_bytes_delta"],
            "external_bytes_delta": value["accounting"]["external_bytes_delta"],
        }, indent=2, sort_keys=True))
    except (GateError, PIPE.PipelineError, STD.StdlibCheckError,
            C.CompileError, B.BytecodeError, B.VMError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-repl-direct-expression: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
