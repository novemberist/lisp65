#!/usr/bin/env python3
"""Permanent ABI, source, and executable gate for C2.2 F2 bitops."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402


CONTRACT = ROOT / "config/c2-bitops-contract.json"
LEDGER = ROOT / "config/bytecode-abi-ledger.json"
VM_H = ROOT / "src/vm.h"
VM_C = ROOT / "src/vm.c"
MODEL = ROOT / "tools/host-lisp/bytecode_p0.py"
COMPILER = ROOT / "tools/host-lisp/bytecode_p0_compiler.py"
LCC = ROOT / "lib/dialect-v2/lcc-profile.lisp"
PUBLIC = ROOT / "lib/dialect-v2/eval-runtime.lisp"
ABI_DOC = ROOT / "docs/contracts/bytecode-abi.md"
ASH_ASM = ROOT / "src/lisp65_ash_tagged.s"
OPS = ((20, "LOGAND", "logand"), (21, "LOGIOR", "logior"),
       (22, "LOGXOR", "logxor"), (23, "ASH", "ash"))


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def bundle() -> dict[str, Any]:
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "ledger": json.loads(LEDGER.read_text(encoding="utf-8")),
        "vm_h": VM_H.read_text(encoding="utf-8"),
        "vm_c": VM_C.read_text(encoding="utf-8"),
        "model": MODEL.read_text(encoding="utf-8"),
        "compiler": COMPILER.read_text(encoding="utf-8"),
        "lcc": LCC.read_text(encoding="utf-8"),
        "public": PUBLIC.read_text(encoding="utf-8"),
        "abi_doc": ABI_DOC.read_text(encoding="utf-8"),
        "ash_asm": ASH_ASM.read_text(encoding="utf-8"),
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    contract = value["contract"]
    require(
        contract["format"] == "lisp65-c2-bitops-contract-v1"
        and contract["call_contract"]["arity"] == "exactly two"
        and contract["value_contract"]["fixnum_min"] == -16384
        and contract["value_contract"]["fixnum_max"] == 16383
        and contract["value_contract"]["ash_count_min"] == -14
        and contract["value_contract"]["ash_count_max"] == 14,
        "F2 value contract drift",
    )
    identities = {
        row["id"]: (row["canonical_name"], row["operand"])
        for row in value["ledger"]["opcode_identities"]
    }
    v1 = next(row for row in value["ledger"]["profiles"]
              if row["id"] == "dialect-v1")
    v2 = next(row for row in value["ledger"]["profiles"]
              if row["id"] == "dialect-v2")
    for ident, upper, lower in OPS:
        require(identities.get(ident) == (upper, "none"),
                f"F2 ledger identity drift: {ident}")
        require(ident not in v1["opcodes"]["active"]
                and ident in v2["opcodes"]["active"],
                f"F2 ABI profile asymmetry drift: {ident}")
        require(re.search(rf"\bOP_{upper}\s*=\s*{ident}\b", value["vm_h"])
                is not None, f"F2 C opcode mirror drift: {upper}")
        require(f"case OP_{upper}:" in value["vm_c"],
                f"F2 C dispatch missing: {upper}")
        require(f'OpSpec({ident}, "{upper}")' in value["model"],
                f"F2 Python decoder missing: {upper}")
        require(f'self.compile_binary(args, "{upper}")' in value["compiler"],
                f"F2 Python compiler missing: {lower}")
        require(f"((eq name '{lower}) {ident})" in value["lcc"],
                f"F2 v2 LCC mirror missing: {lower}")
        require(f"((eq op '{lower}) (%lcc-v2-bitop-binary" in value["lcc"],
                f"F2 v2 LCC lowering missing: {lower}")
        require(
            f"(defun {lower} " in value["public"]
            and f"({lower} a b)" in value["public"]
            if lower != "ash" else
            "(defun ash (value count) (ash value count))" in value["public"],
            f"F2 public wrapper missing: {lower}",
        )
        require(
            re.search(rf"\|\s*{ident}\s*\|\s*`{upper}`\s*\|\s*none\s*\|",
                      value["abi_doc"]) is not None,
            f"F2 live ABI row missing: {upper}",
        )
    require(
        "static __attribute__((noinline)) obj vm_fixbinop" in value["vm_c"]
        and "case OP_LOGAND: case OP_LOGIOR: case OP_LOGXOR: case OP_ASH:"
            in value["vm_c"]
        and "vm_bitop" not in value["vm_c"]
        and "extern obj lisp65_ash_tagged(obj value, obj count);"
            in value["vm_c"]
        and ".section\t.lisp65_resident_island" in value["ash_asm"]
        and ".globl\tlisp65_ash_tagged" in value["ash_asm"]
        and ".type\tlisp65_ash_tagged,@function" in value["ash_asm"]
        and ".size\tlisp65_ash_tagged," in value["ash_asm"]
        and "sta\tvm_status" in value["ash_asm"]
        and value["ash_asm"].count("ldz\t#0") == 2
        and contract["implementation"]["ash_leaf_bytes"] == 112
        and contract["implementation"]["resident_state_bytes"] == 0
        and contract["implementation"]["new_roots"] == 0,
        "F2 shared resident body/ASH leaf/state contract drift",
    )
    return {
        "status": "passed-all-eight-ABI-and-source-views",
        "opcodes": {str(i): upper for i, upper, _lower in OPS},
        "dialect_v1": "reserved",
        "dialect_v2": "active",
        "resident_state_bytes": 0,
        "prim_ids_added": 0,
    }


def mutation_tests(value: dict[str, Any]) -> int:
    mutations: list[dict[str, Any]] = []

    def text_mutation(key: str, old: str, new: str) -> None:
        item = copy.deepcopy(value)
        require(old in item[key], f"F2 mutation anchor absent: {key}:{old}")
        item[key] = item[key].replace(old, new, 1)
        mutations.append(item)

    text_mutation("vm_h", "OP_LOGAND=20", "OP_LOGAND=25")
    text_mutation("vm_c", "case OP_LOGIOR:", "case OP_ADD:")
    text_mutation("model", 'OpSpec(22, "LOGXOR")',
                  'OpSpec(22, "LOGOR")')
    text_mutation("compiler", 'self.compile_binary(args, "ASH")',
                  'self.compile_binary(args, "LOGAND")')
    text_mutation("lcc", "((eq name 'logand) 20)",
                  "((eq name 'logand) 21)")
    text_mutation("lcc", "((eq op 'logxor) (%lcc-v2-bitop-binary",
                  "((eq op 'logxor) (%lcc-binary")
    text_mutation("public", "(defun logior (a b) (logior a b))",
                  "(defun logior (a b) (logand a b))")
    text_mutation("abi_doc", "| 23 | `ASH` | none |",
                  "| 23 | `ASH` | u8 |")
    text_mutation("ash_asm", ".size\tlisp65_ash_tagged,",
                  ".nosize\tlisp65_ash_tagged,")
    text_mutation("ash_asm", ".section\t.lisp65_resident_island",
                  ".section\t.text")
    text_mutation("ash_asm", "sta\tvm_status", "sta\t__rc2")
    text_mutation("ash_asm", "ldz\t#0", "ldz\t#1")

    v1_active = copy.deepcopy(value)
    next(row for row in v1_active["ledger"]["profiles"]
         if row["id"] == "dialect-v1")["opcodes"]["active"].append(20)
    mutations.append(v1_active)
    v2_reserved = copy.deepcopy(value)
    next(row for row in v2_reserved["ledger"]["profiles"]
         if row["id"] == "dialect-v2")["opcodes"]["active"].remove(23)
    mutations.append(v2_reserved)
    bad_count = copy.deepcopy(value)
    bad_count["contract"]["value_contract"]["ash_count_max"] = 15
    mutations.append(bad_count)
    stateful = copy.deepcopy(value)
    stateful["contract"]["implementation"]["resident_state_bytes"] = 1
    mutations.append(stateful)

    for index, item in enumerate(mutations):
        try:
            validate(item)
        except GateError:
            continue
        raise GateError(f"F2 mutation accepted: {index}")
    return len(mutations)


def _runtime() -> tuple[B.Heap, dict[int, B.CodeObject], dict[Any, str], dict]:
    ledger = C._abi_ledger("dialect-v2", None)
    names = [lower for _ident, _upper, lower in OPS]
    heap = C.prepare_heap(names + ["list", "funcall", "apply", "t", "x"])
    directory: dict[int, B.CodeObject] = {}
    code_names: dict[Any, str] = {}
    for lower in names:
        params = "(value count)" if lower == "ash" else "(a b)"
        form = C.parse_one(f"(defun {lower} {params} ({lower} "
                           f"{'value count' if lower == 'ash' else 'a b'}))")
        name, code, helpers = C.compile_top_form_with_helpers(
            form, heap, strict_arity=True,
            abi_profile="dialect-v2", abi_ledger=ledger,
        )
        require(name == lower and not helpers, f"F2 wrapper compile drift: {lower}")
        directory[heap.intern(name)] = code
        code_names[code] = name
    return heap, directory, code_names, ledger


def _add_case(
    heap: B.Heap, directory: dict[int, B.CodeObject],
    code_names: dict[Any, str], ledger: dict, name: str, body: str,
) -> B.CodeObject:
    form = C.parse_one(f"(defun {name} () {body})")
    result_name, code, helpers = C.compile_top_form_with_helpers(
        form, heap, strict_arity=True,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    require(result_name == name and not helpers, f"F2 case compile drift: {name}")
    directory[heap.intern(name)] = code
    code_names[code] = name
    return code


def executable_fixtures() -> dict[str, Any]:
    heap, directory, code_names, ledger = _runtime()
    vm = B.P0VM(
        heap=heap, directory=directory, code_names=code_names,
        abi_profile="dialect-v2", abi_ledger=ledger,
    )
    success = (
        ("logand", "(logand 63 42)", 42),
        ("logior", "(logior 40 2)", 42),
        ("logxor", "(logxor 43 1)", 42),
        ("ash-left", "(ash 21 1)", 42),
        ("ash-right", "(ash -84 -1)", -42),
        ("logand-negative", "(logand -1 42)", 42),
        ("logior-negative", "(logior -43 1)", -43),
        ("logxor-negative", "(logxor -43 1)", -44),
        ("ash-left-low-bound", "(ash -8192 1)", -16384),
        ("ash-left-high-bound", "(ash 8191 1)", 16382),
        ("ash-count-low-bound", "(ash -16384 -14)", -1),
        ("ash-count-high-bound", "(ash -1 14)", -16384),
    )
    rows: list[dict[str, Any]] = []
    for index, (name, expression, expected) in enumerate(success):
        for route in ("direct", "funcall"):
            if route == "direct":
                routed = expression
            else:
                parsed = C.parse_one(expression)
                routed = "(funcall (function %s) %s)" % (
                    parsed[0], " ".join(str(x) for x in parsed[1:]))
            code = _add_case(
                heap, directory, code_names, ledger,
                f"%f2-{index}-{route}", routed,
            )
            result = vm.run(code)
            require(B.is_fix(result) and B.fixval(result) == expected,
                    f"F2 {name}/{route} result drift")
            rows.append({"case": name, "route": route, "result": expected})

    for ident, upper, lower in OPS:
        code = directory[heap.intern(lower)]
        require(ident in code.payload and B.OPCODES[ident].mnemonic == upper,
                f"F2 wrapper does not emit {upper}")
        decoded_v1 = B.classify_abi_id(
            "opcode", ident, profile_id="dialect-v1", abi_ledger=ledger)
        decoded_v2 = B.classify_abi_id(
            "opcode", ident, profile_id="dialect-v2", abi_ledger=ledger)
        require(decoded_v1["status"] == "reserved"
                and decoded_v2["status"] == "active"
                and decoded_v2["canonical_name"] == upper,
                f"F2 decoder profile drift: {upper}")

    apply_cases = (
        ("logand", "63 42", 42),
        ("logior", "40 2", 42),
        ("logxor", "43 1", 42),
        ("ash", "84 -1", 42),
    )
    for index, (name, args, expected) in enumerate(apply_cases):
        code = _add_case(
            heap, directory, code_names, ledger, f"%f2-apply-{index}",
            f"(apply (function {name}) (quote ({args})))",
        )
        result = vm.run(code)
        require(B.is_fix(result) and B.fixval(result) == expected,
                f"F2 {name}/apply result drift")
        rows.append({"case": name, "route": "apply", "result": expected})

    failures = (
        ("count-high", "(ash 1 15)", "TypeError"),
        ("count-low", "(ash 1 -15)", "TypeError"),
        ("overflow-high", "(ash 8192 1)", "TypeError"),
        ("overflow-low", "(ash -8193 1)", "TypeError"),
        ("wrong-type-left", "(logand 'x 1)", "TypeError"),
        ("wrong-type-right", "(logxor 1 'x)", "TypeError"),
    )
    rejected = []
    for index, (name, body, status) in enumerate(failures):
        code = _add_case(
            heap, directory, code_names, ledger, f"%f2-fail-{index}", body)
        try:
            vm.run(code)
        except B.VMError as exc:
            require(exc.status == status, f"F2 {name} status drift: {exc.status}")
        else:
            raise GateError(f"F2 negative accepted: {name}")
        rejected.append({"case": name, "status": status})

    logior = directory[heap.intern("logior")]
    for name, args in (
        ("wrong-arity-low", [B.mkfix(1)]),
        ("wrong-arity-high", [B.mkfix(1), B.mkfix(2), B.mkfix(3)]),
    ):
        try:
            vm.run(logior, args)
        except B.VMError as exc:
            require(exc.status == "ArityError",
                    f"F2 {name} status drift: {exc.status}")
        else:
            raise GateError(f"F2 negative accepted: {name}")
        rejected.append({"case": name, "status": "ArityError"})

    return {
        "status": "passed-direct-funcall-apply-and-negative-fixtures",
        "positive_observations": rows,
        "negative_observations": rejected,
        "positive_count": len(rows),
        "negative_count": len(rejected),
        "dialect_v1_reserved_count": 4,
        "dialect_v2_active_count": 4,
    }


def main() -> int:
    try:
        value = bundle()
        report = validate(value)
        report["mutations_rejected"] = mutation_tests(value)
        report["execution"] = executable_fixtures()
    except (OSError, ValueError, KeyError, GateError, C.CompileError) as exc:
        print(f"c2-bitops-gate: FAIL: {exc}")
        return 1
    print(
        "c2-bitops-gate: PASS "
        f"opcodes={len(OPS)} mutations={report['mutations_rejected']} "
        f"positive={report['execution']['positive_count']} "
        f"negative={report['execution']['negative_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
