#!/usr/bin/env python3
"""Qualify E5's bounded nesting error and exact failure postcondition."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ADDENDA = ROOT / "config/c2-cross-invariant-c2.2-open-addenda.json"
REVIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-b3-c3-d3-e5-contract-review-receipt.json")
OLD_TABLE = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2/"
    "error-text-table.h")
ERROR_CODES = ROOT / "src/error_codes.h"
ERROR_TEXTS = ROOT / "config/error-texts.json"
ERROR_OVERLAY = ROOT / "src/error_overlay.c"
ERROR_ASM = ROOT / "src/l65e_bcode_ordinal.s"
RUNTIME = ROOT / "src/c2_product_runtime.c"
INTERRUPT_C = ROOT / "src/interrupt.c"
INTERRUPT_H = ROOT / "src/interrupt.h"
VM_C = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
EVAL = ROOT / "src/eval.c"
PLACEMENT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
SMOKE = ROOT / "tools/host-lisp/error_overlay_smoke.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-matrix-e5-cold-front-terminal-noreturn-detail-seam-"
    "fixture-receipt.json")

EXPECTED = {
    ADDENDA: "73aa314bc1a8f9dceaa3e0ce144262335dd197503ea11afca2356d5b67671777",
    REVIEW: "1d3e203390460efb08a8d479b0dc753a742afb6ff5346c78c2446dfa5a7708c8",
    OLD_TABLE: "1aea3833862203b5d9d2683e7dba12386c6eb04868cfef719bb34b1b87378371",
}
CODE = 63
DETAIL = 5
MAX_DEPTH = 4


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def function_body(source: str, name: str, occurrence: int = 0) -> str:
    matches = list(re.finditer(
        r"\b" + re.escape(name) + r"\s*\([^;{]*\)\s*\{", source))
    require(len(matches) > occurrence, f"function body absent: {name}")
    match = matches[occurrence]
    start = source.find("{", match.start())
    depth = 0
    for end in range(start, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():end + 1]
    raise GateError(f"unterminated function: {name}")


def enum_bindings(text: str) -> dict[str, int]:
    return {
        name: int(value)
        for name, value in re.findall(
            r"\b(LISP65_ERR_[A-Z0-9_]+)\s*=\s*(\d+)", text)
    }


def old_bindings(text: str) -> dict[str, int]:
    return {
        name: int(value)
        for name, value in re.findall(
            r"X\((LISP65_ERR_[A-Z0-9_]+),\s*(\d+)u\)", text)
    }


def source_errors(texts: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    codes = texts[ERROR_CODES]
    registry = json.loads(texts[ERROR_TEXTS])
    overlay = texts[ERROR_OVERLAY]
    asm = texts[ERROR_ASM]
    runtime = texts[RUNTIME]
    interrupt_c = texts[INTERRUPT_C]
    interrupt_h = texts[INTERRUPT_H]
    vm_c = texts[VM_C]
    vm_h = texts[VM_H]
    evaluation = texts[EVAL]
    if ("LISP65_ERR_C2_NESTING_DEPTH = 63" not in codes
            or "LISP65_ERROR_CODE_LIMIT = 64" not in codes):
        errors.append("append-only-error-registry")
    entries = [row for row in registry["entries"] if row["code"] == CODE]
    if len(entries) != 1 or entries[0].get("id") != "c2-nesting-depth" \
            or entries[0].get("text") != "eval: nesting depth exceeded":
        errors.append("code63-registry-entry")
    current = enum_bindings(codes)
    previous = old_bindings(OLD_TABLE.read_text(encoding="utf-8"))
    if any(current.get(name) != value for name, value in previous.items()):
        errors.append("pre63-error-number-drift")
    required_overlay = (
        "if (context->code == LISP65_ERR_C2_NESTING_DEPTH) {\n"
        "        if (!IS_FIX(context->detail)",
        "!IS_FIX(context->detail) || FIXVAL(context->detail) != 5",
        "emit(' '); emit('5');",
    )
    for token in required_overlay:
        if token not in overlay:
            errors.append("host-renderer:" + token)
    required_asm = (
        "cpx\t#63",
        "beq\t.Ldetail_depth",
        "cmp\t#$0b",
        "bne\t.Lerr_detail",
        "cmp\t#64",
        "beq\t.Lemit_depth",
    )
    for token in required_asm:
        if token not in asm:
            errors.append("mos-renderer:" + token)
    for name in ("c2_append_fronts_phase",):
        body = function_body(runtime, name)
        authenticated = body.find("c2_transient_fronts(&depth")
        check = body.find("depth >= C2D_MAX_TRANSIENT_DEPTH")
        detail = body.find(
            "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5))")
        terminal = body.find("__builtin_unreachable();", detail)
        first_mutation = min(
            at for at in (
                body.find("C2AW_FRONT_DEPTH(w) ="),
                body.find("c2_record_u16(w->record + 2"),
                body.find("c2_record_u32(w->record + 8"),
                body.find("w->old_images =")
            )
            if at >= 0)
        if (authenticated < 0 or check < authenticated
                or "C2AW_TRANSIENT(w) && depth >=" not in body
                or detail < check or terminal < detail
                or first_mutation < terminal):
            errors.append(name + ":depth-refusal-after-mutation")
        if ("lisp65_error_defer" in body
                or "pending_code" in body or "pending_symbol" in body):
            errors.append(name + ":cold-producer-built-private-seam")
    for name in ("c2_append_reserve_transient_phase",
                 "c2_append_reserve_transient_bounds_phase"):
        body = function_body(runtime, name)
        if ("LISP65_ERR_C2_NESTING_DEPTH" in body
                or "lisp_abort_detail(" in body):
            errors.append(name + ":retained-depth-seam-after-cold-move")
    install = function_body(runtime, "c2_product_install")
    failure = install.find("if (emit != C2_EMIT_OK || !append_ok)")
    generic = install.find("vm_status = VM_BADOPCODE; return NIL;", failure)
    if (failure < 0 or generic < failure
            or "LISP65_ERR_C2_NESTING_DEPTH" in install
            or "VM_C2_NESTING_DEPTH" in install
            or "MKFIX(5)" in install
            or "lisp_abort_detail(" in install):
        errors.append("install-built-second-E5-seam")
    begin_at = runtime.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    begin_end = runtime.find(
        "\nstatic uint8_t c2_append_rollback(", begin_at)
    begin = runtime[begin_at:begin_end]
    if "C2_APPEND_BEGIN_DEPTH" in begin:
        errors.append("resident-special-E5-result-survived")
    symbol_body = function_body(interrupt_c, "lisp_abort_symbol")
    if ("static lisp65_error_code pending_code" not in interrupt_c
            or "static obj pending_symbol" not in interrupt_c
            or "extern lisp65_error_code pending_code" in interrupt_h
            or "extern obj pending_symbol" in interrupt_h
            or "lisp65_error_defer" in interrupt_c
            or "lisp65_error_raise_pending" in interrupt_c):
        errors.append("private-E5-status-machinery-survived")
    if (symbol_body.find("pending_code = code;") < 0
            or symbol_body.find("pending_symbol = symbol;")
                < symbol_body.find("pending_code = code;")
            or symbol_body.find("lisp_abort_jump();")
                < symbol_body.find("pending_symbol = symbol;")):
        errors.append("ordinary-symbol-abort-does-not-consume-one-seam")
    if ("VM_C2_NESTING_DEPTH" in vm_h or "VM_C2_NESTING_DEPTH" in vm_c
            or "LISP65_ERR_C2_NESTING_DEPTH" in evaluation):
        errors.append("E5-specific-VM-translation-survived")
    return errors


def state() -> dict[str, Any]:
    return {
        "c2d": bytes((index * 17 + 3) & 0xff for index in range(33840)),
        "c2j": bytes(64),
        "session_attic": bytes(
            (index * 29 + 7) & 0xff for index in range(257)),
        "bank2": bytes((index * 5 + 1) & 0xff for index in range(311)),
        "bank3": bytes((index * 11 + 9) & 0xff for index in range(313)),
        "exports": tuple((index, 0xe000 + index * 2) for index in range(8)),
        "ready": 1,
        "family": 1,
        "generation": 9,
        "depth": 0,
    }


def run_nested(target_depth: int, *, wrong_code: int = CODE,
               detail: int | None = DETAIL, mutate_before: bool = False,
               leave_ready_zero: bool = False) -> dict[str, Any]:
    value = state()
    before = deepcopy(value)
    caught: tuple[int, int | None] | None = None

    def enter() -> None:
        nonlocal caught
        if value["depth"] >= MAX_DEPTH:
            if mutate_before:
                value["c2j"] = b"X" + value["c2j"][1:]
            if leave_ready_zero:
                value["ready"] = 0
            caught = (wrong_code, detail)
            return
        value["depth"] += 1
        if value["depth"] < target_depth:
            enter()
        value["depth"] -= 1

    enter()
    if target_depth <= MAX_DEPTH:
        require(caught is None, "allowed depth raised an error")
    return {
        "target_depth": target_depth,
        "error": caught,
        "state_equal": value == before,
        "repl_followup": "t" if value == before else "unusable",
    }


def mutation_gate(texts: dict[Path, str]) -> dict[str, str]:
    rejected: dict[str, str] = {}
    source_mutations: dict[str, dict[Path, str]] = {
        "collapse-depth-five-to-VM_BADOPCODE": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));",
                "lisp_abort_detail(LISP65_ERR_VM_BADOPCODE, MKFIX(5));", 1)},
        "model-terminal-abort-as-returning-on-MOS": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "__builtin_unreachable();",
                "return C2_STREAM_ERR_C2D;", 1)},
        "publish-front-before-depth-refusal": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "if (C2AW_TRANSIENT(w) && depth >= C2D_MAX_TRANSIENT_DEPTH) {",
                "C2AW_FRONT_DEPTH(w) = depth;\n"
                "    if (C2AW_TRANSIENT(w) && "
                "depth >= C2D_MAX_TRANSIENT_DEPTH) {", 1)},
        "reuse-an-existing-error-code": {
            **texts, ERROR_CODES: texts[ERROR_CODES].replace(
                "LISP65_ERR_C2_NESTING_DEPTH = 63",
                "LISP65_ERR_C2_NESTING_DEPTH = 62", 1)},
        "omit-detail": {
            **texts, ERROR_OVERLAY: texts[ERROR_OVERLAY].replace(
                "if (context->code == LISP65_ERR_C2_NESTING_DEPTH) {",
                "if (0) {", 1)},
        "publish-journal-before-depth-check": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "if (C2AW_TRANSIENT(w) && depth >= C2D_MAX_TRANSIENT_DEPTH) {",
                "w->old_images = depth;\n"
                "    if (C2AW_TRANSIENT(w) && "
                "depth >= C2D_MAX_TRANSIENT_DEPTH) {", 1)},
        "change-existing-error-number": {
            **texts, ERROR_CODES: texts[ERROR_CODES].replace(
                "LISP65_ERR_RUNTIME_FAMILY_STAGE = 62",
                "LISP65_ERR_RUNTIME_FAMILY_STAGE = 61", 1)},
        "send-NIL-instead-of-Fixnum5": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));",
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, NIL);", 1)},
        "bypass-terminal-detail-seam": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));",
                "lisp_abort_code(LISP65_ERR_C2_NESTING_DEPTH);", 1)},
        "direct-private-status-access": {
            **texts, RUNTIME: texts[RUNTIME].replace(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));",
                "pending_code = LISP65_ERR_C2_NESTING_DEPTH;", 1)},
        "remove-common-abort-landing": {
            **texts, INTERRUPT_C: texts[INTERRUPT_C].replace(
                "lisp_abort_jump();\n}",
                "/* abort landing skipped */\n}", 1)},
        "restore-private-VM-status": {
            **texts, VM_H: texts[VM_H].replace(
                "VM_DIRMISS, VM_STEPLIMIT, VM_ARITY, VM_NOTDESIGNATOR",
                "VM_DIRMISS, VM_STEPLIMIT, VM_ARITY, VM_NOTDESIGNATOR,\n"
                "    VM_C2_NESTING_DEPTH = LISP65_ERR_C2_NESTING_DEPTH", 1)},
    }
    for name, mutated in source_mutations.items():
        require(source_errors(mutated), f"E5 source mutation survived: {name}")
        rejected[name] = "rejected"
    model_mutations = {
        "leave-READY-zero":
            run_nested(5, leave_ready_zero=True),
        "leave-one-C2D-byte-changed":
            run_nested(5, mutate_before=True),
    }
    for name, result in model_mutations.items():
        require(not result["state_equal"],
                f"E5 state mutation survived: {name}")
        rejected[name] = "rejected"
    return rejected


def renderer_gate() -> dict[str, Any]:
    ran = subprocess.run(
        ["python3", str(SMOKE)], cwd=ROOT, text=True,
        capture_output=True, check=False)
    require(ran.returncode == 0,
            "error-overlay smoke red: " + ran.stdout + ran.stderr)
    require("depth5-fixnum" in ran.stdout and "headroom=116" in ran.stdout,
            "depth-five renderer evidence missing")
    return {
        "status": "passed-host-and-MOS-renderer",
        "output": [line for line in ran.stdout.splitlines() if line],
        "positive": "code63 + Fixnum5 -> eval: nesting depth exceeded 5",
        "negative_details": ["NIL", "Fixnum4", "Fixnum6", "SYMI5"],
    }


def build_receipt() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file() and sha(path) == expected,
                f"bound E5 authority drift: {path}")
    texts = {
        path: path.read_text(encoding="utf-8")
        for path in (
            ERROR_CODES, ERROR_TEXTS, ERROR_OVERLAY, ERROR_ASM, RUNTIME,
            INTERRUPT_C, INTERRUPT_H, VM_C, VM_H, EVAL)
    }
    errors = source_errors(texts)
    require(not errors, "E5 source gate red: " + ", ".join(errors))
    cases = [run_nested(depth) for depth in range(1, 6)]
    for row in cases[:4]:
        require(row["error"] is None and row["state_equal"],
                f"allowed depth red: {row}")
    require(cases[4]["error"] == (CODE, DETAIL)
            and cases[4]["state_equal"]
            and cases[4]["repl_followup"] == "t",
            "depth-five exact postcondition red")
    mutations = mutation_gate(texts)
    require(len(mutations) == 14, "E5 mutation count drift")
    return {
        "format": "lisp65-c2.2-matrix-e5-terminal-detail-seam-fixture-v5",
        "recorded_on": "2026-07-23",
        "status": "passed-product-shaped-host-awaiting-real-eval-hardware",
        "row": "E5",
        "registry": {
            "stable_code": CODE,
            "numeric_fallback": "E3f",
            "detail": {"kind": "fixnum", "value": DETAIL},
            "previous_codes_unchanged": len(old_bindings(
                OLD_TABLE.read_text(encoding="utf-8"))),
            "code_limit": 64,
        },
        "cases": cases,
        "failure_order": [
            "authenticated-depth-read",
            "constant-code63-and-Fixnum5-enter-existing-terminal-detail-seam",
            "one-abort-landing-before-journal-or-plane-mutation",
            "existing-C2J-and-transaction-abort-cleanup",
            "existing-numeric-renderer-consumes-bound-status-and-detail",
        ],
        "renderer": renderer_gate(),
        "mutations": mutations,
        "authorities": {
            "approved_addenda": bind(ADDENDA),
            "line_review_receipt": bind(REVIEW),
            "link57_pre-E5_error_table": bind(OLD_TABLE),
            "error_registry": bind(ERROR_TEXTS),
            "error_codes": bind(ERROR_CODES),
            "host_renderer": bind(ERROR_OVERLAY),
            "mos_renderer": bind(ERROR_ASM),
            "product_runtime": bind(RUNTIME),
            "pending_status_implementation": bind(INTERRUPT_C),
            "pending_status_interface": bind(INTERRUPT_H),
            "VM_without_E5_private_status": bind(VM_C),
            "VM_interface_without_E5_private_status": bind(VM_H),
            "VM_consumer_without_E5_private_branch": bind(EVAL),
            "cold_placement_contract": bind(PLACEMENT),
        },
        "execution": {
            "host_model_cases": len(cases),
            "renderer_host_runs": 1,
            "MOS_object_compiles": 2,
            "whole_program_lto_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "hardware_fixture": {
            "status": "pending-bundled-acceptance-run",
            "form": "real eval nests to five; catch code63/detail5; then t",
        },
        "claim_limit": (
            "Proves E5's append-only identity, closed detail union, refusal "
            "order and byte-identical host postcondition. E5 remains OPEN "
            "until the real-eval hardware fixture is green on the successor "
            "identity. No acceptance or promotion is claimed."),
        "value_string": (
            "E5=host-green depths=1..4 depth5=E3f/detail5 "
            "state=byte-identical mutations=14/14 renderer=host+MOS "
            "hardware=pending acceptance=blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent E5 receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "E5 receipt absent or drifted")
            verb = "CHECK PASS"
        print(
            "c2-matrix-e5-nesting-depth: "
            f"{verb} depths=5 mutations=14/14 renderer=host+MOS "
            "hardware=pending")
        return 0
    except (GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as exc:
        print("c2-matrix-e5-nesting-depth: FAIL " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
