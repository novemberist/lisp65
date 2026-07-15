#!/usr/bin/env python3
"""Check profile-bound v2 Prim-ID lowering without executing the VM."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
from v2_native_function_views_generated import (  # noqa: E402
    ACTIVE_CALLPRIMS, FUNCTION_DESIGNATOR_IDS,
)


V1_PRIMS = dict(C.PRIM_CALLS)
V2_PRIMS = dict(ACTIVE_CALLPRIMS)
CASES = (
    ("nreverse", 23, 1, "(defun f (x) (nreverse x))"),
    ("rplaca", 24, 2, "(defun f (x y) (rplaca x y))"),
    ("rplacd", 25, 2, "(defun f (x y) (rplacd x y))"),
    ("%string-codes", 28, 1, "(defun f (string) (%string-codes string))"),
    ("%string-from-codes", 29, 1, "(defun f (codes) (%string-from-codes codes))"),
)
SERVICE_ARITIES = {
    "%cs-read-open": 1, "%fasl-read-form": 0, "%fasl-stage": 2,
    "%fasl-stage-get": 1, "%set-macro": 2,
    "function-kind": 1, "gensym": 0, "lcc-install": 2,
    "macroexpand-1": 1, "prin1": 1,
    "symbol-count": 0, "symbol-max": 0, "symbol-name": 1, "write-char": 1,
    **{name: 0 for prim_id, name in B.PRIM_IDS.items() if 46 <= prim_id <= 56},
    "boundp": 1,
    "%list-malformed-error": 0,
    "set": 2,
    "key-event": 0,
    "peek": 2,
    "poke": 3,
}


class LoweringError(RuntimeError):
    pass


def _ledger() -> dict:
    with (ROOT / "config" / "bytecode-abi-ledger.json").open(encoding="utf-8") as source:
        return json.load(source)


def _pairs(text: str) -> dict[str, int]:
    pairs = re.findall(r'\{\s*"([^"]+)"\s*,\s*([0-9]+)\s*\}', text)
    result = {name: int(prim_id) for name, prim_id in pairs}
    if len(result) != len(pairs):
        raise LoweringError("duplicate primitive mapping")
    return result


def _c_prims(v2: bool) -> dict[str, int]:
    command = [os.environ.get("HOSTCC", "cc"), "-E", "-P", "-Isrc"]
    if v2:
        command.append("-DLISP65_DIALECT_V2")
    command.append("src/compile.c")
    result = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True,
    )
    match = re.search(r"\bPRIMS\[\]\s*=\s*\{(.*?)\};", result.stdout, re.S)
    if not match:
        raise LoweringError("cannot find preprocessed src/compile.c PRIMS")
    return _pairs(match.group(1))


def _defun(text: str, name: str) -> str:
    start = text.find("(defun " + name)
    if start < 0:
        raise LoweringError("missing LCC definition: " + name)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise LoweringError("unterminated LCC definition: " + name)


def _lcc_prims() -> dict[str, int]:
    text = (ROOT / "lib" / "dialect-v2" / "lcc-profile.lisp").read_text(
        encoding="utf-8"
    )
    body = "".join(
        _defun(text, name)
        for name in (
            "%lcc-prim", "%lcc-v2-prim2", "%lcc-v2-prim3", "%lcc-v2-prim4",
        )
    )
    pairs = re.findall(r"\(\(eq name '([^\s()]+)\)\s+([0-9]+)\)", body)
    result = {name: int(prim_id) for name, prim_id in pairs}
    if len(result) != len(pairs):
        raise LoweringError("duplicate v2 LCC primitive mapping")
    return result


def _check_python(ledger: dict) -> None:
    if C.PRIM_CALLS != V1_PRIMS or C.PRIM_CALLS_V2 != V2_PRIMS:
        raise LoweringError("Python compiler profile table drift")
    for name, prim_id, argc, source in CASES:
        _entry, code = C.compile_source(
            source, B.Heap(), strict_arity=True, abi_profile="dialect-v2",
            abi_ledger=ledger,
        )
        if bytes((61, prim_id, argc)) not in code.payload:
            raise LoweringError("Python v2 lowering drift: " + name)
    for name, argc in SERVICE_ARITIES.items():
        prim_id = V2_PRIMS[name]
        params = " ".join(f"x{i}" for i in range(argc))
        args = (" " + params) if params else ""
        _entry, code = C.compile_source(
            f"(defun f ({params}) ({name}{args}))", B.Heap(),
            strict_arity=True, abi_profile="dialect-v2", abi_ledger=ledger,
        )
        if bytes((61, prim_id, argc)) not in code.payload:
            raise LoweringError("Python v2 service lowering drift: " + name)
    for name, prim_id in (("string->list", 1), ("list->string", 2)):
        heap = B.Heap()
        _entry, code = C.compile_source(
            f"(defun f (x) ({name} x))", heap,
            strict_arity=True, abi_profile="dialect-v2", abi_ledger=ledger,
        )
        if bytes((61, prim_id, 1)) in code.payload or 62 not in code.payload:
            raise LoweringError("Python v2 emitted a tombstoned Prim-ID: " + name)
        if len(code.littab) != 1 or heap.symbol_name(code.littab[0]) != name:
            raise LoweringError("Python v2 tombstone did not degrade to a named CALL")
    for name, prim_id, params, args in (
        ("%string-slice", 26, "s start end", "s start end"),
        ("%string-concat-list", 27, "strings", "strings"),
        ("%save-staged", 34, "name length", "name length"),
        ("number->string", 40, "x", "x"),
    ):
        heap = B.Heap()
        _entry, code = C.compile_source(
            f"(defun f ({params}) ({name} {args}))", heap,
            strict_arity=True, abi_profile="dialect-v2", abi_ledger=ledger,
        )
        if bytes((61, prim_id, len(params.split()))) in code.payload or 62 not in code.payload:
            raise LoweringError(f"Python v2 emitted retired Prim-ID {prim_id}")
        if len(code.littab) != 1 or heap.symbol_name(code.littab[0]) != name:
            raise LoweringError(f"Python v2 {name} did not lower to a named CALL")
    for prim_id in B.INTERNAL_ONLY_PRIM_IDS:
        if B.prim_is_function_designator(
            prim_id, profile_id="dialect-v2", abi_ledger=ledger
        ):
            raise LoweringError("internal string capability became a function designator")
    actual_designators = {
        prim_id for prim_id in V2_PRIMS.values()
        if B.prim_is_function_designator(
            prim_id, profile_id="dialect-v2", abi_ledger=ledger
        )
    }
    if actual_designators != set(FUNCTION_DESIGNATOR_IDS):
        raise LoweringError("registry function-designator classification drift")
    try:
        C.compile_source(
            "(defun f () nil)", B.Heap(), strict_arity=False,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
    except C.CompileError:
        pass
    else:
        raise LoweringError("profile/strict-arity mismatch was accepted")


def _expect_vm_error(label: str, status: str, action) -> None:
    try:
        action()
    except B.VMError as exc:
        if exc.status == status:
            return
        raise LoweringError(f"{label} returned {exc.status}, expected {status}") from exc
    raise LoweringError(label + " was accepted")


def _check_python_vm(ledger: dict) -> None:
    heap = B.Heap()
    vm = B.P0VM(heap=heap, abi_profile="dialect-v2", abi_ledger=ledger)

    def call(prim_id: int, args: list[int]) -> int:
        return vm._callprim(prim_id, len(args), list(args))

    dotted = heap.cons(B.mkfix(1), heap.cons(B.mkfix(2), B.mkfix(9)))
    if heap.obj_to_text(call(23, [dotted])) != "(2 1)":
        raise LoweringError("Python VM nreverse dotted-prefix drift")
    pair = heap.cons(B.mkfix(1), B.NIL)
    if call(24, [pair, B.mkfix(7)]) != pair or heap.car(pair) != B.mkfix(7):
        raise LoweringError("Python VM rplaca drift")
    if call(25, [pair, B.mkfix(8)]) != pair or heap.cdr(pair) != B.mkfix(8):
        raise LoweringError("Python VM rplacd drift")

    source = heap.string_from_text("abcdef")
    codes = call(28, [source])
    if heap.obj_to_text(codes) != "(97 98 99 100 101 102)":
        raise LoweringError("Python VM string codes drift")
    if heap.string_to_text(call(29, [codes])) != "abcdef":
        raise LoweringError("Python VM string from codes drift")

    for prim_id, args in (
        (26, [source, B.mkfix(1), B.mkfix(4)]),
        (27, [B.NIL]),
    ):
        saved = list(args)
        _expect_vm_error(
            f"Python VM retired string Prim-ID {prim_id}", "BadOpcode",
            lambda prim_id=prim_id, args=args: vm._callprim(prim_id, len(args), args),
        )
        if args != saved:
            raise LoweringError(f"Python VM Prim-ID {prim_id} consumed arguments")

    tombstone_stack = [source]
    _expect_vm_error(
        "Python VM v2 tombstone", "BadOpcode",
        lambda: vm._callprim(1, 1, tombstone_stack),
    )
    if tombstone_stack != [source]:
        raise LoweringError("Python VM tombstone consumed arguments before rejection")
    retired_stack = [B.mkfix(-123)]
    _expect_vm_error(
        "Python VM retired number->string", "BadOpcode",
        lambda: vm._callprim(40, 1, retired_stack),
    )
    if retired_stack != [B.mkfix(-123)]:
        raise LoweringError("Python VM Prim-ID 40 tombstone consumed its argument")
    save_stack = [source, B.mkfix(17)]
    _expect_vm_error(
        "Python VM retired %save-staged", "BadOpcode",
        lambda: vm._callprim(34, 2, save_stack),
    )
    if save_stack != [source, B.mkfix(17)]:
        raise LoweringError("Python VM Prim-ID 34 tombstone consumed its arguments")
    _expect_vm_error(
        "Python VM internal function designator", "DirMiss",
        lambda: vm._invoke_function(
            heap.intern("%string-slice"), [source, B.mkfix(0), B.mkfix(1)]
        ),
    )


def main() -> int:
    ledger = _ledger()
    checks = {
        "c-v1": _c_prims(False),
        "c-v2": _c_prims(True),
        "lcc-v2": _lcc_prims(),
    }
    expected = {"c-v1": V1_PRIMS, "c-v2": V2_PRIMS, "lcc-v2": V2_PRIMS}
    for label, actual in checks.items():
        if actual != expected[label]:
            raise LoweringError(
                f"{label} profile map drift: actual={actual} expected={expected[label]}"
            )
    _check_python(ledger)
    _check_python_vm(ledger)
    print(
        "v2-prim-lowering: PASS profiles=3 lowerings=30 runtime=7 "
        "tombstones=6 internal=27 staging_services=25"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LoweringError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print("v2-prim-lowering: FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
