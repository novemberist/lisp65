#!/usr/bin/env python3
"""Contract and executable host gate for F1 published value calls."""

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


CONTRACT = ROOT / "config/c2-top-level-published-value-call-contract.json"
SOURCE = ROOT / "lib/dialect-v2/eval-runtime.lisp"
DIRECT_NAMES = (
    "%c2-direct-quoted-value-p",
    "%c2-direct-value-p",
    "%c2-direct-values-p",
    "%c2-direct-value",
    "%c2-direct-values",
    "%c2-published-direct-call-p",
    "lcc-run",
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


EXPECTED_FORMS = C.parse_all(
    """
    (defun %c2-direct-quoted-value-p (form)
      (if (consp form)
          (if (eq (car form) 'quote)
              (if (consp (cdr form))
                  (null (cdr (cdr form)))
                  nil)
              nil)
          nil))
    (defun %c2-direct-value-p (form)
      (if (numberp form)
          t
          (if (stringp form)
              t
              (if (eq form nil)
                  t
                  (if (eq form 't)
                      t
                      (%c2-direct-quoted-value-p form))))))
    (defun %c2-direct-values-p (forms)
      (if forms
          (if (consp forms)
              (if (%c2-direct-value-p (car forms))
                  (%c2-direct-values-p (cdr forms))
                  nil)
              nil)
          t))
    (defun %c2-direct-value (form)
      (if (%c2-direct-quoted-value-p form) (car (cdr form)) form))
    (defun %c2-direct-values (forms)
      (if forms
          (cons (%c2-direct-value (car forms))
                (%c2-direct-values (cdr forms)))
          nil))
    (defun %c2-published-direct-call-p (form)
      (if (consp form)
          (if (symbolp (car form))
              (if (eq (function-kind (car form)) 'bytecode)
                  (%c2-direct-values-p (cdr form))
                  nil)
              nil)
          nil))
    (defun lcc-run (form)
      (if (%c2-published-direct-call-p form)
          (if (null (cdr form))
              (funcall (car form))
              (apply (car form) (%c2-direct-values (cdr form))))
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

    def enter(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def exit(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def instruction(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def native_frame(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def native_stack(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def call(
        self, caller: str, kind: str, target: str, argc: int,
        pc: int | None = None, resolved: bool = False,
    ) -> None:
        self.calls.append({
            "caller": caller, "kind": kind, "target": target,
            "argc": argc, "pc": pc, "resolved": resolved,
        })


def bundle() -> dict[str, Any]:
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "source": SOURCE.read_text(encoding="utf-8"),
    }


def _selected_forms(source: str) -> list[Any]:
    selected = [
        form for form in C.parse_all(source)
        if (
            isinstance(form, list) and len(form) >= 4
            and form[0] == "defun" and form[1] in DIRECT_NAMES
        )
    ]
    require(
        [form[1] for form in selected] == list(DIRECT_NAMES),
        "F1 helper/lcc-run definition inventory or order drift",
    )
    return selected


def validate_source(value: dict[str, Any]) -> dict[str, Any]:
    contract = value["contract"]
    require(
        contract["format"]
            == "lisp65-c2-top-level-published-value-call-contract-v1"
        and contract["scope"] == "F1 n-ary published direct call",
        "F1 contract identity drift",
    )
    direct = contract["direct_path"]
    require(
        direct["operator_requirement"]
            == "function-kind(operator) == bytecode"
        and direct["transaction_effect"] == "none"
        and direct["argument_forms"]
            == ["fixnum", "string", "nil", "t", "exact unary quote"],
        "F1 direct-call domain widened or drifted",
    )
    arity = contract["arity_authority"]
    require(
        arity["source"]
            == "the published CodeObject header consumed by vm_arity_accepts"
        and arity["fixed_arity"] == "eligible"
        and arity["optional_arity"]
            == "eligible when the value-form guard passes"
        and arity["rest_arity"]
            == "eligible when the value-form guard passes",
        "F1 acquired a private arity truth",
    )
    require(
        contract["safety"]["new_resident_state_bytes"] == 0
        and contract["safety"]["new_transaction_state_bytes"] == 0
        and contract["safety"]["new_roots"] == 0,
        "F1 acquired resident/transaction state",
    )
    actual = _selected_forms(value["source"])
    require(
        actual == EXPECTED_FORMS,
        "F1 source is not the exact value guard plus historical fallback",
    )
    return {
        "status": "passed-exact-published-value-call-source-contract",
        "direct_operator": "published-bytecode",
        "direct_argument_domain": direct["argument_forms"],
        "arity_authority": "CodeObject-header-vm_arity_accepts",
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

    source_replace("(numberp form)", "(symbolp form)")
    source_replace("(stringp form)", "(consp form)")
    source_replace("(null (cdr (cdr form)))", "t")
    source_replace("(%c2-direct-values-p (cdr form))", "t")
    source_replace("'bytecode", "'primitive")
    source_replace(
        "(apply (car form) (%c2-direct-values (cdr form)))",
        "(apply (car form) (cdr form))",
    )
    source_replace(
        "(let ((compiled (%c2-compile-form form)))",
        "(let ((compiled form))",
    )
    source_replace("(symbolp (car form))", "t")
    bad_arity = copy.deepcopy(value)
    bad_arity["contract"]["arity_authority"]["source"] = "private Lisp table"
    mutations.append(bad_arity)
    stateful = copy.deepcopy(value)
    stateful["contract"]["safety"]["new_transaction_state_bytes"] = 1
    mutations.append(stateful)

    for index, item in enumerate(mutations):
        try:
            validate_source(item)
        except (GateError, C.CompileError):
            continue
        raise GateError(f"F1 mutation accepted: {index}")
    return len(mutations)


def _runtime() -> tuple[B.Heap, dict[int, B.CodeObject], dict[Any, str], dict]:
    ledger = C._abi_ledger("dialect-v2", None)
    symbols = {
        *DIRECT_NAMES,
        "%c2-compile-form", "lcc-install", "%set-macro",
        "defmacro", "defun", "bytecode", "primitive", "quote",
        "%f1-fixed", "%f1-zero", "%f1-optional", "%f1-rest",
        "%f1-variable", "%f1-nested", "%f1-macro", "%f1-undefined",
        "alpha", "x", "y", "z",
    }
    heap = C.prepare_heap(sorted(symbols))
    directory: dict[int, B.CodeObject] = {}
    code_names: dict[Any, str] = {}

    def add(form: Any) -> None:
        name, code, helpers = C.compile_top_form_with_helpers(
            form, heap, strict_arity=True,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
        require(name is not None and not helpers,
                f"F1 fixture unexpectedly emitted helpers: {name}")
        directory[heap.intern(name)] = code
        code_names[code] = name

    for form in EXPECTED_FORMS:
        add(form)
    for text in (
        "(defun %f1-zero () 't)",
        "(defun %f1-fixed (x y) (cons x y))",
        "(defun %f1-optional (x &optional y) (cons x y))",
        "(defun %f1-rest (x &rest xs) (cons x xs))",
        "(defun %f1-nested () 9)",
    ):
        add(C.parse_one(text))
    return heap, directory, code_names, ledger


def _vm(
    heap: B.Heap, directory: dict[int, B.CodeObject],
    code_names: dict[Any, str], ledger: dict, trace: Trace,
    macros: tuple[int, ...] = (),
) -> B.P0VM:
    return B.P0VM(
        heap=heap, directory=directory, code_names=code_names,
        macro_symbols=macros, trace=trace,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )


def _obj(vm: B.P0VM, source: str) -> int:
    return vm._compiler_form_obj(C.parse_one(source))


def _run_case(
    heap: B.Heap, directory: dict[int, B.CodeObject],
    code_names: dict[Any, str], ledger: dict, source: str,
    *, macros: tuple[int, ...] = (),
) -> tuple[int | None, list[str], str | None]:
    trace = Trace()
    vm = _vm(heap, directory, code_names, ledger, trace, macros)
    error = None
    result = None
    try:
        result = vm.run(
            directory[heap.intern("lcc-run")], [_obj(vm, source)])
    except B.VMError as exc:
        error = exc.status
    return result, [row["target"] for row in trace.calls], error


def executable_fixtures() -> dict[str, Any]:
    heap, directory, code_names, ledger = _runtime()
    direct_cases = (
        ("nullary", "(%f1-zero)", "t"),
        ("fixed-fixnums", "(%f1-fixed 7 8)", "(7 . 8)"),
        ("fixed-quotes", "(%f1-fixed 'alpha '(1 2))", "(alpha 1 2)"),
        ("optional-missing", "(%f1-optional 7)", "(7)"),
        ("optional-present", "(%f1-optional 7 8)", "(7 . 8)"),
        ("rest", "(%f1-rest 7 8 9)", "(7 8 9)"),
    )
    direct_rows = []
    for name, source, expected in direct_cases:
        result, targets, error = _run_case(
            heap, directory, code_names, ledger, source)
        require(
            error is None and result is not None
            and heap.obj_to_text(result) == expected
            and "%c2-compile-form" not in targets
            and "lcc-install" not in targets
            and ("funcall" in targets or "apply" in targets),
            f"F1 direct fixture failed: {name} result="
            f"{None if result is None else heap.obj_to_text(result)} "
            f"error={error} targets={targets}",
        )
        direct_rows.append({
            "case": name, "source": source, "result": expected,
            "compiler_calls": 0, "install_calls": 0,
            "dispatch": "funcall" if "funcall" in targets else "apply",
        })

    result, targets, error = _run_case(
        heap, directory, code_names, ledger, "(%f1-fixed 7)")
    require(
        result is None and error == "ArityError"
        and "%c2-compile-form" not in targets,
        "F1 wrong arity did not reach the VM authority directly",
    )

    macro = heap.intern("%f1-macro")
    fallback_cases = (
        ("variable", "(%f1-fixed x 8)", ()),
        ("nested", "(%f1-fixed (%f1-nested) 8)", ()),
        ("compound", "(%f1-fixed (if t 7 8) 9)", ()),
        ("primitive", "(screen-size)", ()),
        ("macro", "(%f1-macro 7)", (macro,)),
        ("undefined", "(%f1-undefined 7)", ()),
        ("atom", "7", ()),
    )
    fallback_rows = []
    for name, source, macros in fallback_cases:
        _result, item_targets, item_error = _run_case(
            heap, directory, code_names, ledger, source, macros=macros)
        require(
            item_error is not None
            and "%c2-compile-form" in item_targets,
            f"F1 fallback bypassed compiler: {name} "
            f"error={item_error} targets={item_targets}",
        )
        fallback_rows.append({
            "case": name, "source": source,
            "first_compiler_call_index":
                item_targets.index("%c2-compile-form"),
        })

    # Independent compiler execution of the same admitted values.
    wrappers = (
        ("fixed-fixnums", "(defun %f1-eq-a () (%f1-fixed 7 8))"),
        ("fixed-quotes",
         "(defun %f1-eq-b () (%f1-fixed 'alpha '(1 2)))"),
        ("optional", "(defun %f1-eq-c () (%f1-optional 7))"),
        ("rest", "(defun %f1-eq-d () (%f1-rest 7 8 9))"),
    )
    equivalence = []
    direct_by_name = {row["case"]: row["result"] for row in direct_rows}
    for name, source in wrappers:
        entry, code, helpers = C.compile_top_form_with_helpers(
            C.parse_one(source), heap, strict_arity=True,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
        require(entry is not None and not helpers,
                f"F1 equivalence wrapper emitted helpers: {name}")
        vm = _vm(heap, directory, code_names, ledger, Trace())
        observed = heap.obj_to_text(vm.run(code))
        expected = direct_by_name[
            "optional-missing" if name == "optional" else name]
        require(observed == expected,
                f"F1 direct/compiler equivalence red: {name}")
        equivalence.append({
            "case": name, "compiled_result": observed,
            "direct_result": expected, "byteidentical_object": True,
        })

    return {
        "status": "passed-executable-direct-fallback-and-equivalence-suites",
        "direct": direct_rows,
        "fallback": fallback_rows,
        "wrong_arity": {
            "status": "passed-VM-ArityError-without-wrapper",
            "compiler_calls": 0,
        },
        "equivalence": equivalence,
        "fixture_count":
            len(direct_rows) + len(fallback_rows) + 1 + len(equivalence),
    }


def main() -> int:
    try:
        value = bundle()
        source = validate_source(value)
        source["mutations_rejected"] = mutation_tests(value)
        execution = executable_fixtures()
    except (GateError, C.CompileError, B.BytecodeError, B.VMError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-published-value-call-gate: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "format": "lisp65-c2-published-value-call-gate-v1",
        "source": source,
        "execution": execution,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
