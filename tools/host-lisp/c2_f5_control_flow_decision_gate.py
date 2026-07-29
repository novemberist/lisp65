#!/usr/bin/env python3
"""Gate the F5 control-flow decision against the real C2-lite unwind."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-control-flow-repair-decision.json"
NOTE = ROOT / "docs/planning/c2.2-f5-while-vs-catch-throw-contract-probe.md"
VM_H = ROOT / "src/vm.h"
VM_C = ROOT / "src/vm.c"
COMPILER_C = ROOT / "src/compile.c"
COMPILER_PY = ROOT / "tools/host-lisp/bytecode_p0_compiler.py"
INTERRUPT_C = ROOT / "src/interrupt.c"
REPL_C = ROOT / "src/repl.c"
RUNTIME_H = ROOT / "src/c2_product_runtime.h"
UNWIND = ROOT / "config/c2-nested-append-unwind-contract.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-f5-while-catch-throw-design-probe-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def validate(contract: dict[str, Any]) -> dict[str, Any]:
    scope = contract["scope"]
    decision = contract["decision"]
    taxonomy = contract["taxonomy"]
    while_contract = contract["while_contract"]
    c2 = contract["c2_lite_evidence"]
    future = contract["future_boundary"]

    require(
        contract["format"] == "lisp65-c2-control-flow-repair-decision-v1"
        and contract["status"]
        == "owner-accepted-paper-decision-implementation-not-authorized"
        and scope["phase"] == "F5"
        and scope["product_source_changes_authorized"] == 0
        and scope["product_links_authorized"] == 0
        and scope["hardware_runs"] == 0,
        "F5 scope or identity drift",
    )
    require(
        decision["selected"] == "while"
        and decision["rejected_for_this_cut"] == "catch/throw"
        and taxonomy["planning_label"] == "one control-flow repair"
        and "not a non-local-exit" in taxonomy["correction"]
        and future["no_dual_mechanism"] is True,
        "F5 selection or taxonomy drift",
    )
    require(
        while_contract["syntax"] == "(while test form*)"
        and while_contract["result"] == "NIL after normal termination"
        and while_contract["lowering"].startswith(
            "both device and host compilers use the existing JFALSEREL")
        and len(while_contract["excluded"]) == 6,
        "while surface/lowering drift",
    )
    require(
        "no authenticated runtime-overlay transaction remains active"
        in c2["transaction_rule"]
        and "longjmp to the sole REPL top-level landing"
        in c2["abort_shape"]
        and "not catch frames" in c2["transient_shape"],
        "C2-lite unwind classification drift",
    )

    vm_h = VM_H.read_text(encoding="utf-8")
    vm_c = VM_C.read_text(encoding="utf-8")
    compiler_c = COMPILER_C.read_text(encoding="utf-8")
    compiler_py = COMPILER_PY.read_text(encoding="utf-8")
    interrupt_c = INTERRUPT_C.read_text(encoding="utf-8")
    repl_c = REPL_C.read_text(encoding="utf-8")
    runtime_h = RUNTIME_H.read_text(encoding="utf-8")
    unwind = load(UNWIND)

    require(
        "OP_JMPREL=28" in vm_h and "OP_JFALSEREL=29" in vm_h
        and "case OP_JMPREL:" in vm_c and "case OP_JFALSEREL:" in vm_c,
        "existing relative-branch VM ABI missing",
    )
    require(
        "static void compile_dotimes" in compiler_c
        and "static void compile_dolist" in compiler_c
        and "OP_JFALSEREL" in compiler_c and "OP_JMPREL" in compiler_c
        and "def compile_dotimes" in compiler_py
        and "def compile_dolist" in compiler_py
        and 'self.emit("JFALSEREL", 0)' in compiler_py
        and 'self.emit("JMPREL", 0)' in compiler_py,
        "two-compiler loop-lowering evidence missing",
    )
    require(
        'op_is(op, "while")' not in compiler_c
        and 'op == "while"' not in compiler_py
        and 'op_is(op, "catch")' not in compiler_c
        and 'op_is(op, "throw")' not in compiler_c
        and 'op == "catch"' not in compiler_py
        and 'op == "throw"' not in compiler_py,
        "paper-only F5 surface leaked into a compiler",
    )
    require(
        interrupt_c.count("longjmp(lisp_toplevel, 1)") == 1
        and interrupt_c.index("(void)c2_product_abort_cleanup()")
        < interrupt_c.index("longjmp(lisp_toplevel, 1)")
        and repl_c.count("setjmp(lisp_toplevel)") == 1
        and "this is the sole\n * bridge from every error/RUN-STOP longjmp source"
        in runtime_h,
        "top-level abort landing evidence drift",
    )
    require(
        unwind["semantic_decision"]["transaction_rule"].lower().startswith(
            c2["transaction_rule"].lower())
        and unwind["unwind_journal"]["longjmp_cleanup"].startswith(
            "The central abort landing validates the journal")
        and unwind["c2d_v4"]["transient_suffix"]["maximum_depth"] == 4,
        "C2J/transient authority drift",
    )
    require(len(contract["required_future_while_proof"]) == 8,
            "future while proof inventory drift")
    require(len(contract["catch_throw_cost"]["required_new_truths"]) == 5,
            "catch/throw cost inventory drift")
    return {
        "status": "passed-real-C2-lite-unwind-and-compiler-evidence",
        "selected": decision["selected"],
        "taxonomy": taxonomy["planning_label"],
        "existing_branch_opcodes": [28, 29],
        "compiler_loop_witnesses": ["device-dotimes", "device-dolist",
                                    "host-dotimes", "host-dolist"],
        "top_level_setjmp_count": 1,
        "top_level_longjmp_count": 1,
        "new_product_bytes": 0,
        "hardware_runs": 0,
    }


def mutation_tests(contract: dict[str, Any]) -> int:
    rejected = 0

    def reject(change: Callable[[dict[str, Any]], None]) -> None:
        nonlocal rejected
        candidate = copy.deepcopy(contract)
        change(candidate)
        try:
            validate(candidate)
        except GateError:
            rejected += 1
        else:
            raise GateError("F5 mutation survived")

    reject(lambda c: c["decision"].update(selected="catch/throw"))
    reject(lambda c: c["decision"].update(rejected_for_this_cut="while"))
    reject(lambda c: c["taxonomy"].update(
        planning_label="one minimal non-local-exit primitive"))
    reject(lambda c: c["taxonomy"].update(
        correction="while is a non-local-exit primitive"))
    reject(lambda c: c["while_contract"].update(result="last body value"))
    reject(lambda c: c["while_contract"].update(
        lowering="add a resident WHILE opcode"))
    reject(lambda c: c["future_boundary"].update(no_dual_mechanism=False))
    reject(lambda c: c["scope"].update(product_links_authorized=1))
    reject(lambda c: c["scope"].update(hardware_runs=1))
    reject(lambda c: c["c2_lite_evidence"].update(
        transient_shape="transient records are catch frames"))
    return rejected


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def main() -> int:
    try:
        contract = load(CONTRACT)
        proof = validate(contract)
        proof["mutations_rejected"] = mutation_tests(contract)
        receipt = {
            "format": "lisp65-c2.2-f5-control-flow-design-probe-receipt-v1",
            "recorded_on": "2026-07-27",
            "status": "passed-owner-accepted-paper-decision",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "decision": proof,
            "claim_limit": (
                "Paper decision only. No language surface, product byte, "
                "capacity, hardware or performance claim."
            ),
            "authority": {
                "contract": bind(CONTRACT),
                "note": bind(NOTE),
                "vm_h": bind(VM_H),
                "vm_c": bind(VM_C),
                "device_compiler": bind(COMPILER_C),
                "host_compiler": bind(COMPILER_PY),
                "interrupt": bind(INTERRUPT_C),
                "repl": bind(REPL_C),
                "runtime_h": bind(RUNTIME_H),
                "unwind_contract": bind(UNWIND),
                "gate": bind(Path(__file__)),
            },
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2 F5 control-flow decision gate: PASS "
            f"selected={proof['selected']} "
            f"mutations={proof['mutations_rejected']} "
            "product-bytes=0 hardware=0"
        )
        return 0
    except (GateError, KeyError, ValueError, OSError) as exc:
        print(f"c2 F5 control-flow decision gate: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
