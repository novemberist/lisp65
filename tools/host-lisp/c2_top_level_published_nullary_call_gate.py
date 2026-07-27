#!/usr/bin/env python3
"""Contract and executable host gate for the C2 nullary published-call path."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402


CONTRACT = ROOT / "config/c2-top-level-published-nullary-call-contract.json"
SOURCE = ROOT / "lib/dialect-v2/eval-runtime.lisp"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


EXPECTED_LCC_RUN = C.parse_one(
    """
    (defun lcc-run (form)
      (if (if (consp form)
              (if (null (cdr form))
                  (eq (function-kind (car form)) 'bytecode)
                  nil)
              nil)
          (funcall (car form))
          (let ((compiled (%c2-compile-form form)))
            (cond ((if (consp form) (eq (car form) 'defmacro) nil)
                   (%set-macro (car (cdr form))
                               (lcc-install compiled nil)))
                  ((if (consp form) (eq (car form) 'defun) nil)
                   (lcc-install compiled (car (cdr form))))
                  (t (lcc-install compiled 't))))))
    """
)


class Trace:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def enter(self, name: str, code: B.CodeObject, args: list[int]) -> None:
        del name, code, args

    def exit(self, name: str, code: B.CodeObject) -> None:
        del name, code

    def instruction(
        self, name: str, code: B.CodeObject, pc: int,
        spec: B.OpSpec, operand: Any,
    ) -> None:
        del name, code, pc, spec, operand

    def call(
        self, caller: str, kind: str, target: str, argc: int,
        pc: int | None = None, resolved: bool = False,
    ) -> None:
        self.calls.append({
            "caller": caller, "kind": kind, "target": target,
            "argc": argc, "pc": pc, "resolved": resolved,
        })

    def native_frame(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def native_stack(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs


def bundle() -> dict[str, Any]:
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "source": SOURCE.read_text(encoding="utf-8"),
    }


def _lcc_run(source: str) -> list[Any]:
    matches = [
        form for form in C.parse_all(source)
        if (
            isinstance(form, list) and len(form) >= 4
            and form[0] == "defun" and form[1] == "lcc-run"
        )
    ]
    require(len(matches) == 1, "lcc-run must have exactly one definition")
    return matches[0]


def validate_source(value: dict[str, Any]) -> dict[str, Any]:
    contract = value["contract"]
    require(
        contract["format"]
            == "lisp65-c2-top-level-published-nullary-call-contract-v1"
        and contract["problem"]["completed_latency_attempts"] == 1
        and contract["problem"]["remaining_latency_attempts"] == 1,
        "published-nullary contract identity/accounting drift",
    )
    fast = contract["fast_path"]
    require(
        fast["argument_count"] == 0
        and fast["operator_requirement"]
            == "function-kind(operator) == bytecode"
        and fast["transaction_effect"] == "none",
        "published-nullary fast-path scope widened",
    )
    require(
        contract["safety"]["new_resident_state_bytes"] == 0
        and contract["safety"]["new_transaction_state_bytes"] == 0
        and contract["safety"]["new_roots"] == 0,
        "published-nullary path acquired state",
    )
    actual = _lcc_run(value["source"])
    require(
        actual == EXPECTED_LCC_RUN,
        "lcc-run is not the exact singleton-bytecode guard plus historical "
        "fallback",
    )
    return {
        "status": "passed-exact-published-nullary-source-contract",
        "direct_shape": "proper singleton list",
        "direct_kind": "bytecode",
        "direct_action": "funcall canonical operator binding",
        "fallback_preserved": True,
        "new_resident_state_bytes": 0,
    }


def mutation_tests(value: dict[str, Any]) -> int:
    mutations: list[dict[str, Any]] = []

    def source_replace(old: str, new: str) -> None:
        item = copy.deepcopy(value)
        require(old in item["source"], f"mutation anchor absent: {old}")
        item["source"] = item["source"].replace(old, new, 1)
        mutations.append(item)

    source_replace("(null (cdr form))", "(consp (cdr form))")
    source_replace("'bytecode", "'primitive")
    source_replace("(funcall (car form))", "(lcc-install (car form) nil)")
    source_replace(
        "(if (if (consp form)",
        "(if (if (symbolp form)",
    )
    source_replace(
        "(let ((compiled (%c2-compile-form form)))",
        "(let ((compiled form))",
    )
    widened = copy.deepcopy(value)
    widened["contract"]["fast_path"]["argument_count"] = 1
    mutations.append(widened)
    stateful = copy.deepcopy(value)
    stateful["contract"]["safety"]["new_transaction_state_bytes"] = 1
    mutations.append(stateful)

    for index, item in enumerate(mutations):
        try:
            validate_source(item)
        except (GateError, C.CompileError):
            continue
        raise GateError(f"published-nullary mutation accepted: {index}")
    return len(mutations)


def _compile_runtime() -> tuple[B.Heap, B.CodeObject, B.CodeObject, dict]:
    ledger = C._abi_ledger("dialect-v2", None)
    heap = C.prepare_heap((
        "lcc-run", "%published-target", "%c2-compile-form",
        "lcc-install", "%set-macro", "defmacro", "defun",
        "bytecode", "primitive", "screen-size",
    ))
    _name, lcc_run, helpers = C.compile_top_form_with_helpers(
        EXPECTED_LCC_RUN, heap, strict_arity=True,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    require(not helpers, "lcc-run host fixture unexpectedly emitted helpers")
    target_form = C.parse_one("(defun %published-target () 't)")
    _name, target, helpers = C.compile_top_form_with_helpers(
        target_form, heap, strict_arity=True,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    require(not helpers, "published target unexpectedly emitted helpers")
    return heap, lcc_run, target, ledger


def _form(heap: B.Heap, *items: int) -> int:
    result = B.NIL
    for item in reversed(items):
        result = heap.cons(item, result)
    return result


def executable_fixtures() -> dict[str, Any]:
    heap, lcc_run, target, ledger = _compile_runtime()
    lcc_sym = heap.intern("lcc-run")
    target_sym = heap.intern("%published-target")
    directory = {lcc_sym: lcc_run, target_sym: target}

    trace = Trace()
    vm = B.P0VM(
        heap=heap, directory=directory, trace=trace,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    expected = vm.run(target)
    trace.calls.clear()
    observed = vm.run(lcc_run, [_form(heap, target_sym)])
    targets = [row["target"] for row in trace.calls]
    require(
        observed == expected == heap.t_obj
        and "function-kind" in targets
        and "funcall" in targets
        and "%published-target" in targets
        and "%c2-compile-form" not in targets
        and "lcc-install" not in targets,
        "published nullary call did not bypass compile/install exactly",
    )

    fallback_cases = (
        ("one_argument_bytecode",
         _form(heap, target_sym, B.mkfix(7)), ()),
        ("nullary_primitive",
         _form(heap, heap.intern("screen-size")), ()),
        ("nullary_macro",
         _form(heap, heap.intern("%fixture-macro")),
         (heap.intern("%fixture-macro"),)),
        ("nullary_undefined",
         _form(heap, heap.intern("%fixture-undefined")), ()),
    )
    fallback_rows: list[dict[str, Any]] = []
    for name, form, macros in fallback_cases:
        item_trace = Trace()
        item_directory = dict(directory)
        if macros:
            item_directory[macros[0]] = target
        item_vm = B.P0VM(
            heap=heap, directory=item_directory, macro_symbols=macros,
            trace=item_trace, abi_profile="dialect-v2", abi_ledger=ledger,
        )
        try:
            item_vm.run(lcc_run, [form])
        except B.VMError:
            pass
        else:
            raise GateError(f"fallback fixture unexpectedly completed: {name}")
        item_targets = [row["target"] for row in item_trace.calls]
        require(
            "%c2-compile-form" in item_targets
            and "%published-target" not in item_targets,
            f"mandatory fallback bypassed compiler: {name}",
        )
        fallback_rows.append({
            "case": name,
            "first_compiler_call_index":
                item_targets.index("%c2-compile-form"),
            "result": "passed-through-historical-compiler-edge",
        })

    return {
        "status": "passed-executable-p0-direct-and-fallback-fixtures",
        "direct": {
            "result": heap.obj_to_text(observed),
            "call_targets": targets,
            "compiler_calls": 0,
            "install_calls": 0,
        },
        "fallbacks": fallback_rows,
        "fixtures": 1 + len(fallback_rows),
    }


def main() -> int:
    try:
        value = bundle()
        source = validate_source(value)
        source["mutations_rejected"] = mutation_tests(value)
        execution = executable_fixtures()
    except (GateError, C.CompileError, B.BytecodeError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-top-level-published-nullary-call-gate: FAIL: "
            + str(error),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({
        "format": "lisp65-c2-top-level-published-nullary-call-gate-v1",
        "source": source,
        "execution": execution,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
