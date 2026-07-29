#!/usr/bin/env python3
"""Permanent source and executable gate for the C2.2 F3 shared carrier."""

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


CONTRACT = ROOT / "config/c2-state-error-carrier-contract.json"
OLD_CONTRACT = ROOT / "config/v11-g-state-error-contract.json"
PUBLIC = ROOT / "lib/dialect-v2/eval-runtime.lisp"
BUFFER_H = ROOT / "src/buffer_overlay.h"
BUFFER_C = ROOT / "src/buffer_overlay.c"
ERROR_H = ROOT / "src/error_codes.h"
ERROR_C = ROOT / "src/error_overlay.c"
ERROR_ASM = ROOT / "src/l65e_bcode_ordinal.s"
ERROR_TABLE = ROOT / "config/error-texts.json"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def bundle() -> dict[str, Any]:
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "old_contract": json.loads(OLD_CONTRACT.read_text(encoding="utf-8")),
        "public": PUBLIC.read_text(encoding="utf-8"),
        "buffer_h": BUFFER_H.read_text(encoding="utf-8"),
        "buffer_c": BUFFER_C.read_text(encoding="utf-8"),
        "error_h": ERROR_H.read_text(encoding="utf-8"),
        "error_c": ERROR_C.read_text(encoding="utf-8"),
        "error_asm": ERROR_ASM.read_text(encoding="utf-8"),
        "error_table": json.loads(ERROR_TABLE.read_text(encoding="utf-8")),
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    contract = value["contract"]
    old = value["old_contract"]
    require(
        contract["format"] == "lisp65-c2-state-error-carrier-contract-v1"
        and contract["carrier"]["primitive_id"] == 63
        and contract["carrier"]["resident_dispatcher_added"] is False
        and contract["carrier"]["resident_state_bytes"] == 0
        and contract["carrier"]["new_roots"] == 0,
        "F3 carrier contract drift",
    )
    require(
        old["features"]["room"]["result"]
        == contract["public_functions"]["room"]["result_order"]
        and old["features"]["gc"]["result"].startswith("t after exactly one")
        and old["features"]["error"]["argument"] == "String",
        "F3 changed a pinned 1.1 semantic",
    )
    for selector, name in ((4, "GC"), (5, "ROOM"), (6, "ERROR")):
        require(
            f"#define LISP65_BUFFER_READ_{name}" in value["buffer_h"]
            and f" {selector}" in value["buffer_h"].split(
                f"#define LISP65_BUFFER_READ_{name}", 1)[1].splitlines()[0]
            and f"case LISP65_BUFFER_READ_{name}:" in value["buffer_c"],
            f"F3 selector/source drift: {name}",
        )
    require(
        "#define LISP65_BUFFER_PRIM_READ 63u" in value["buffer_h"]
        and "LISP65_BUFFER_PRIM_LAST LISP65_C1_COMPILER_PRIM"
            in value["buffer_h"]
        and 'section(".lisp65_rt_buffer_read")' in value["buffer_c"]
        and "(defun gc ()" in value["public"]
        and "(if (%buffer-read 4 nil) 't nil)" in value["public"]
        and "(defun room ()" in value["public"]
        and "(%buffer-read 5 nil)" in value["public"]
        and "(defun error (message)" in value["public"]
        and "(%buffer-read 6 message)" in value["public"],
        "F3 single-carrier/public-wrapper drift",
    )
    room = value["buffer_c"].split(
        "static BUFFER_READ_ENTRY uint8_t buffer_room", 1)[1].split(
            "BUFFER_READ_ENTRY uint8_t lisp65_buffer_overlay_read_entry", 1)[0]
    require(
        all(needle in room for needle in (
            "values[0] = mem_free_cells();",
            "values[1] = MAX_CELLS;",
            "values[2] = (uint16_t)(sym_max() - sym_count());",
            "values[3] = sym_max();",
            "values[4] = (uint16_t)(sym_pool_capacity() - sym_pool_used());",
            "values[5] = sym_pool_capacity();",
            "values[6] = (uint16_t)(vm_dir_capacity() - vm_dir_count());",
            "values[7] = vm_dir_capacity();",
        ))
        and room.index("values[7]") < room.index("GC_CAN_RESERVE")
        and "GC_PUSH(NIL);" in room
        and "GC_SET(GC_TOP, result);" in room
        and "GC_POPN(1);" in room
        and "return VM_HEAPOOM;" in room,
        "F3 room snapshot/root/OOM contract drift",
    )
    gc_case = value["buffer_c"].split(
        "case LISP65_BUFFER_READ_GC:", 1)[1].split(
            "case LISP65_BUFFER_READ_ROOM:", 1)[0]
    require(
        gc_case.count("gc_collect();") == 1
        and "context->result = MKFIX(1);" in gc_case,
        "F3 gc collection/result drift",
    )
    error_case = value["buffer_c"].split(
        "case LISP65_BUFFER_READ_ERROR:", 1)[1].split("default:", 1)[0]
    require(
        "cell_type(context->args[1]) != T_STR" in error_case
        and "LISP65_ERR_USER_MESSAGE" in error_case
        and "lisp_abort_symbol(LISP65_ERR_USER_MESSAGE, context->args[1]);"
            in error_case
        and "context->result = context->args[1];" in error_case,
        "F3 error producer/type transport drift",
    )
    rows = {row["code"]: row for row in value["error_table"]["entries"]}
    require(
        "LISP65_ERR_USER_MESSAGE = 64" in value["error_h"]
        and "LISP65_ERROR_CODE_LIMIT = 65" in value["error_h"]
        and rows[64]["profiles"] == ["host", "workbench"]
        and rows[64]["reason"].startswith(
            "The table row preserves dense code identity")
        and "context->code == LISP65_ERR_USER_MESSAGE" in value["error_c"]
        and "jmp\tl65e_emit_user_string" in value["error_asm"]
        and ".size\tl65e_emit_user_string," in value["error_asm"],
        "F3 append-only dynamic String renderer drift",
    )
    return {
        "status": "passed-one-cold-carrier-and-existing-error-seam",
        "primitive_id": 63,
        "selectors": {"4": "gc", "5": "room", "6": "error"},
        "resident_dispatcher_added": False,
        "resident_state_bytes": 0,
        "new_roots": 0,
    }


def mutation_tests(value: dict[str, Any]) -> int:
    mutations: list[dict[str, Any]] = []

    def text(key: str, old: str, new: str) -> None:
        item = copy.deepcopy(value)
        require(old in item[key], f"F3 mutation anchor absent: {key}:{old}")
        item[key] = item[key].replace(old, new, 1)
        mutations.append(item)

    text("buffer_h", "LISP65_BUFFER_READ_GC      4",
         "LISP65_BUFFER_READ_GC      7")
    text("buffer_h", "#define LISP65_BUFFER_PRIM_READ 63u",
         "#define LISP65_BUFFER_PRIM_READ 67u")
    text("buffer_c", "case LISP65_BUFFER_READ_ROOM:",
         "case LISP65_BUFFER_READ_LENGTH:")
    text("buffer_c", "values[7] = vm_dir_capacity();",
         "values[7] = values[6];")
    text("buffer_c", "GC_PUSH(NIL);", "/* no root */")
    text("buffer_c", "return VM_HEAPOOM;", "return VM_OK;")
    text("buffer_c", "gc_collect();", "/* collection skipped */")
    text("buffer_c", "cell_type(context->args[1]) != T_STR",
         "cell_type(context->args[1]) != T_SYM")
    text("buffer_c", "lisp_abort_symbol(LISP65_ERR_USER_MESSAGE,",
         "lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION,")
    text("public", "(%buffer-read 4 nil)", "(%buffer-read 5 nil)")
    text("public", "(%buffer-read 5 nil)", "(%buffer-read 6 nil)")
    text("public", "(%buffer-read 6 message)", "(%buffer-read 6 nil)")
    text("error_h", "LISP65_ERR_USER_MESSAGE = 64",
         "LISP65_ERR_USER_MESSAGE = 63")
    text("error_c", "context->code == LISP65_ERR_USER_MESSAGE",
         "context->code == LISP65_ERR_UNDEFINED_FUNCTION")
    text("error_asm", "jmp\tl65e_emit_user_string",
         "jmp\tl65e_emit_bcode_ordinal")
    text("error_asm", ".size\tl65e_emit_user_string,",
         ".nosize\tl65e_emit_user_string,")

    stateful = copy.deepcopy(value)
    stateful["contract"]["carrier"]["resident_state_bytes"] = 1
    mutations.append(stateful)
    dispatcher = copy.deepcopy(value)
    dispatcher["contract"]["carrier"]["resident_dispatcher_added"] = True
    mutations.append(dispatcher)
    reordered = copy.deepcopy(value)
    reordered["contract"]["public_functions"]["room"]["result_order"][0:2] = [
        "heap-capacity", "heap-free"]
    mutations.append(reordered)

    for index, item in enumerate(mutations):
        try:
            validate(item)
        except GateError:
            continue
        raise GateError(f"F3 mutation accepted: {index}")
    return len(mutations)


def _compile(
    source: str, heap: B.Heap, directory: dict[int, B.CodeObject],
    names: dict[Any, str], ledger: dict[str, Any],
) -> B.CodeObject:
    form = C.parse_one(source)
    name, code, helpers = C.compile_top_form_with_helpers(
        form, heap, strict_arity=True,
        abi_profile="dialect-v2", abi_ledger=ledger)
    require(not helpers, f"F3 fixture emitted helper: {name}")
    directory[heap.intern(name)] = code
    names[code] = name
    return code


def executable_fixtures() -> dict[str, Any]:
    ledger = C._abi_ledger("dialect-v2", None)
    heap = C.prepare_heap(
        ["gc", "room", "error", "funcall", "apply", "t", "%buffer-read"])
    directory: dict[int, B.CodeObject] = {}
    names: dict[Any, str] = {}
    for source in (
        "(defun gc () (if (%buffer-read 4 nil) 't nil))",
        "(defun room () (%buffer-read 5 nil))",
        "(defun error (message) (%buffer-read 6 message))",
    ):
        _compile(source, heap, directory, names, ledger)
    vm = B.P0VM(
        heap=heap, directory=directory, code_names=names,
        abi_profile="dialect-v2", abi_ledger=ledger)

    positives: list[dict[str, Any]] = []
    for index, (route, body) in enumerate((
        ("direct", "(gc)"),
        ("funcall", "(funcall (function gc))"),
        ("apply", "(apply (function gc) '())"),
    )):
        code = _compile(
            f"(defun %f3-gc-{index} () {body})",
            heap, directory, names, ledger)
        result = vm.run(code)
        require(result == heap.t_obj, f"F3 gc/{route} did not return t")
        positives.append({"function": "gc", "route": route, "result": "t"})

    for index, (route, body) in enumerate((
        ("direct", "(room)"),
        ("funcall", "(funcall (function room))"),
        ("apply", "(apply (function room) '())"),
    )):
        code = _compile(
            f"(defun %f3-room-{index} () {body})",
            heap, directory, names, ledger)
        raw = vm._list_to_objs(vm.run(code), "F3 room")
        require(
            len(raw) == 8 and all(B.is_fix(item) for item in raw),
            f"F3 room/{route} result is not eight fixnums",
        )
        observed = [B.fixval(item) for item in raw]
        require(
            all(0 <= observed[i] <= observed[i + 1]
                for i in range(0, 8, 2)),
            f"F3 room/{route} free/capacity pair drift",
        )
        positives.append({
            "function": "room", "route": route,
            "result": observed,
        })

    for index, (route, body) in enumerate((
        ("direct", '(error "boom")'),
        ("funcall", '(funcall (function error) "boom")'),
        ("apply", '(apply (function error) \'("boom"))'),
    )):
        code = _compile(
            f"(defun %f3-error-{index} () {body})",
            heap, directory, names, ledger)
        try:
            vm.run(code)
        except B.VMError as exc:
            require(
                exc.status == "UserError"
                and exc.error_code == 64
                and heap.string_to_text(exc.error_symbol) == "boom",
                f"F3 error/{route} detail drift",
            )
        else:
            raise GateError(f"F3 error/{route} returned")
        positives.append({
            "function": "error", "route": route,
            "status": "UserError", "code": 64, "detail": "boom",
        })

    negatives: list[dict[str, Any]] = []
    for index, (name, body, status) in enumerate((
        ("error-non-string", "(error 7)", "TypeError"),
        ("gc-extra-arg", "(gc 1)", "ArityError"),
        ("room-extra-arg", "(room 1)", "ArityError"),
        ("error-no-arg", "(error)", "ArityError"),
        ("error-extra-arg", '(error "a" "b")', "ArityError"),
        ("selector-high", "(%buffer-read 7 nil)", "TypeError"),
    )):
        code = _compile(
            f"(defun %f3-negative-{index} () {body})",
            heap, directory, names, ledger)
        try:
            vm.run(code)
        except B.VMError as exc:
            require(exc.status == status,
                    f"F3 {name} status drift: {exc.status}")
        else:
            raise GateError(f"F3 negative accepted: {name}")
        negatives.append({"case": name, "status": status})

    return {
        "status": "passed-nine-routes-and-six-negative-fixtures",
        "positive_observations": positives,
        "negative_observations": negatives,
        "positive_count": len(positives),
        "negative_count": len(negatives),
    }


def main() -> int:
    try:
        value = bundle()
        report = validate(value)
        report["mutations_rejected"] = mutation_tests(value)
        report["execution"] = executable_fixtures()
    except (OSError, ValueError, KeyError, GateError, C.CompileError) as exc:
        print(f"c2-state-error-carrier-gate: FAIL: {exc}")
        return 1
    print(
        "c2-state-error-carrier-gate: PASS "
        f"mutations={report['mutations_rejected']} "
        f"positive={report['execution']['positive_count']} "
        f"negative={report['execution']['negative_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
